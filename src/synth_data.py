"""
Synthetic time-series generator for HAST meter data.

Frank's CSVs (per Zählernummer) have these columns:

    Timestamp, Energy (kWh), Volume flow (l/h), Power (kW),
    Temperature difference (°C), Flow temperature (°C),
    Return temperature (°C), Volume (m³)

Energy and Volume are cumulative; everything else is hourly.

We synthesise ~1 year of hourly data per HAST, conditioned on the
contracted load (Anschlusswert from Nodes_Edges.ods). For a configurable
fraction of HAST we inject one of the known fault patterns:

  * fouled_filter      - flow restriction trending down over months
  * excess_rt          - return temperature too high (poor cooling)
  * continuous_flow    - flow never drops to zero in summer
  * oversized_contract - peak power << contracted (chronic over-spec)
  * control_hysteresis - flow oscillates around setpoint, ΔT noisy

The injection labels are written to a `faults_truth.csv` so we can later
score classifier predictions against them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


FAULT_TYPES = (
    "healthy",
    "fouled_filter",
    "excess_rt",
    "continuous_flow",
    "oversized_contract",
    "control_hysteresis",
)


@dataclass
class MeterSpec:
    zaehlernummer: int
    address: str
    anschlusswert_kw: float
    fault: str = "healthy"


def synth_meter(spec: MeterSpec,
                start: str = "2024-01-01",
                periods: int = 24 * 365,
                seed: Optional[int] = None) -> pd.DataFrame:
    """Generate one year of hourly data for a single HAST.

    Returns the same 8-column schema Frank described. Cumulative energy
    and volume are integrated from the synthetic hourly power and flow.
    """
    rng = np.random.default_rng(seed if seed is not None else spec.zaehlernummer)
    ts = pd.date_range(start, periods=periods, freq="h")

    # ------------------------------------------------------------------
    # 1) Outdoor temperature: seasonal sine + diurnal cycle + noise
    # ------------------------------------------------------------------
    day_of_year = ts.dayofyear + ts.hour / 24
    hour = ts.hour

    t_out = (
        9.0
        - 11 * np.cos(2 * np.pi * day_of_year / 365.25)        # season
        - 4 * np.cos(2 * np.pi * (hour - 14) / 24)             # diurnal
        + rng.normal(0, 1.6, periods)                           # weather noise
    )

    # ------------------------------------------------------------------
    # 2) Heat demand power (kW)
    #    Heating limit ~15 °C; below that, demand grows linearly with ΔT.
    #    Plus a ~constant DHW baseline (~3 % of contracted, capped).
    # ------------------------------------------------------------------
    heating_limit = 15.0
    delta = np.maximum(0, heating_limit - t_out)
    # Scale so peak winter use ~70 % of contracted load (typical sizing margin)
    heating_kw = (delta / 22.0) * spec.anschlusswert_kw * 0.7
    # DHW is bursty: ~10 % of hours have a draw, the rest are zero.
    # Two daily peaks (morning shower, evening cooking/bath).
    morning = (hour >= 6) & (hour <= 9)
    evening = (hour >= 18) & (hour <= 21)
    base_p = np.where(morning | evening, 0.20, 0.05)
    has_draw = rng.random(periods) < base_p
    dhw_peak = np.clip(0.30 * spec.anschlusswert_kw, 1.5, 12.0)
    dhw_kw = np.where(has_draw, dhw_peak * (0.4 + 0.6 * rng.random(periods)), 0.0)
    power_kw = heating_kw + dhw_kw

    # Night setback: lower demand 22:00-05:00 unless cold
    night_mask = (hour >= 22) | (hour < 5)
    power_kw = np.where(night_mask & (t_out > -2), power_kw * 0.6, power_kw)

    # ------------------------------------------------------------------
    # 3) Network supply temperature (Vorlauf):
    #    weather-compensated curve, 70 °C at -10 °C OAT, 55 °C at +15 °C
    # ------------------------------------------------------------------
    t_flow = np.clip(70 - 0.6 * (t_out + 10), 50, 80) + rng.normal(0, 0.6, periods)

    # Design ΔT - typical district heating value is ~30 K at peak
    dt_design = 30.0
    # Actual ΔT depends on load: at low loads the building secondary
    # circuit doesn't cool the water as effectively.
    load_frac = power_kw / max(spec.anschlusswert_kw, 1.0)
    dt = dt_design * (0.45 + 0.55 * np.clip(load_frac, 0, 1)) + rng.normal(0, 0.8, periods)
    dt = np.clip(dt, 3, 45)
    t_return = t_flow - dt

    # Volume flow l/h from Q = m * c * dT (m in kg/h ≈ l/h for water)
    # P [kW] = (m [kg/h] * 4.187 [kJ/kgK] * dT [K]) / 3600 -> m = P*3600/(4.187*dT)
    flow_lh = np.where(power_kw > 0.05,
                       power_kw * 3600 / (4.187 * dt),
                       rng.normal(0, 2, periods))
    flow_lh = np.maximum(flow_lh, 0)

    # ------------------------------------------------------------------
    # 4) Inject the configured fault pattern
    # ------------------------------------------------------------------
    flow_lh, t_return, dt, power_kw = _inject_fault(
        spec.fault, ts, flow_lh, t_flow, t_return, dt, power_kw,
        spec.anschlusswert_kw, rng,
    )

    # ------------------------------------------------------------------
    # 5) Cumulative energy and volume (the real meter exports them this way)
    # ------------------------------------------------------------------
    energy_kwh = np.cumsum(power_kw)              # P is hourly so kWh per step
    volume_m3 = np.cumsum(flow_lh / 1000.0)       # l/h * 1h = l, /1000 = m³

    out = pd.DataFrame({
        "Timestamp": ts,
        "Energy (kWh)": energy_kwh.round(2),
        "Volume flow (l/h)": flow_lh.round(0),
        "Power (kW)": power_kw.round(3),
        "Temperature difference (°C)": dt.round(1),
        "Flow temperature (°C)": t_flow.round(1),
        "Return temperature (°C)": t_return.round(1),
        "Volume (m³)": volume_m3.round(3),
    })
    return out


# --- fault injection -------------------------------------------------------

def _inject_fault(fault, ts, flow_lh, t_flow, t_return, dt, power_kw,
                  anschluss_kw, rng):
    """Mutate one or more channels to embed a known fault signature."""
    n = len(ts)

    if fault == "healthy":
        return flow_lh, t_return, dt, power_kw

    if fault == "fouled_filter":
        # Filter slowly clogs starting Feb -> flow constrained, ΔT widens,
        # delivered power drops below demand. Real signature in the data:
        # flow saturates at a falling ceiling.
        progress = np.clip(np.linspace(-0.2, 1.0, n), 0, 1)
        cap = anschluss_kw * 3600 / (4.187 * 30) * (1.0 - 0.55 * progress)
        flow_lh = np.minimum(flow_lh, cap)
        # Recompute dt from the constrained flow
        new_dt = np.where(flow_lh > 5,
                          power_kw * 3600 / (4.187 * np.maximum(flow_lh, 1)),
                          dt)
        new_dt = np.clip(new_dt, 3, 60)
        t_return = t_flow - new_dt
        return flow_lh, t_return, new_dt, power_kw

    if fault == "excess_rt":
        # Bad cooling on the secondary side -> RT consistently 8-15 °C
        # higher than it should be, especially at part-load.
        bias = 8 + 5 * (1 - np.clip(power_kw / anschluss_kw, 0, 1))
        bias += rng.normal(0, 1.0, n)
        t_return = t_return + bias
        new_dt = t_flow - t_return
        new_dt = np.clip(new_dt, 1, 45)
        # Need more flow to deliver the same power -> raise flow
        flow_lh = np.where(power_kw > 0.05,
                           power_kw * 3600 / (4.187 * np.maximum(new_dt, 1)),
                           flow_lh)
        return flow_lh, t_return, new_dt, power_kw

    if fault == "continuous_flow":
        # Stuck valve / failed shutoff: nonzero flow even in summer when
        # there's no demand. About 30-60 l/h baseline year-round.
        baseline = 40 + 20 * rng.random(n)
        flow_lh = np.maximum(flow_lh, baseline)
        # Phantom return-temperature warming because hot water keeps moving
        idx = power_kw < 0.5
        t_return = np.where(idx, t_flow - 6 - rng.normal(0, 1, n), t_return)
        dt = t_flow - t_return
        # Update power consistent with flow*dt
        power_kw = np.where(idx,
                            flow_lh * 4.187 * dt / 3600,
                            power_kw)
        return flow_lh, t_return, dt, power_kw

    if fault == "oversized_contract":
        # Customer rarely uses more than 30 % of contracted load.
        # We just rescale demand down, leaving Anschlusswert untouched.
        factor = 0.30
        power_kw = power_kw * factor
        flow_lh = np.where(dt > 1, power_kw * 3600 / (4.187 * dt), flow_lh * factor)
        return flow_lh, t_return, dt, power_kw

    if fault == "control_hysteresis":
        # Actuator is sticky / undertuned: flow oscillates around the
        # setpoint with a noticeable limit cycle. ΔT therefore noisy.
        limit_cycle = 0.18 * np.sin(2 * np.pi * np.arange(n) / 6)  # 6 h period
        limit_cycle += 0.12 * np.sin(2 * np.pi * np.arange(n) / 23)
        flow_lh = flow_lh * (1 + limit_cycle) + rng.normal(0, 8, n)
        flow_lh = np.maximum(flow_lh, 0)
        new_dt = np.where(flow_lh > 5,
                          power_kw * 3600 / (4.187 * np.maximum(flow_lh, 1)),
                          dt)
        t_return = t_flow - new_dt
        return flow_lh, t_return, new_dt, power_kw

    raise ValueError(f"Unknown fault type: {fault}")


# --- batch generator -------------------------------------------------------

def generate_dataset(nodes_df: pd.DataFrame,
                     out_dir: Path,
                     fault_share: float = 0.25,
                     seed: int = 42) -> pd.DataFrame:
    """Synthesize one CSV per Zählernummer and a faults-truth manifest.

    `nodes_df` is the loaded `Nodes_Edges.ods` Nodes sheet (uses
    Zählernummer + Anschlusswert + address). About `fault_share` of
    HAST get a non-healthy fault drawn uniformly at random.
    """
    out_dir = Path(out_dir)
    csv_dir = out_dir / "meters"
    csv_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    truth = []
    fault_options = [f for f in FAULT_TYPES if f != "healthy"]

    for _, row in nodes_df.iterrows():
        zid = int(row["Zählernummer"])
        kw = float(row["Anschlusswert"])
        addr = str(row["Straße"])
        fault = "healthy"
        if rng.random() < fault_share:
            fault = rng.choice(fault_options)
        spec = MeterSpec(zaehlernummer=zid, address=addr,
                         anschlusswert_kw=kw, fault=fault)
        df = synth_meter(spec, seed=zid + seed)
        df.to_csv(csv_dir / f"{zid}.csv", index=False)
        truth.append({"Zählernummer": zid, "address": addr,
                      "anschlusswert_kw": kw, "fault": fault})

    truth_df = pd.DataFrame(truth)
    truth_df.to_csv(out_dir / "faults_truth.csv", index=False)
    return truth_df


# --- CLI -------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/raw/synthetic", type=Path,
                   help="output directory")
    p.add_argument("--fault-share", type=float, default=0.25)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    from . import load_data as ld
    nodes = ld.load_logical_nodes()
    truth = generate_dataset(nodes, args.out,
                             fault_share=args.fault_share, seed=args.seed)
    print(f"wrote {len(truth)} meter CSVs to {args.out / 'meters'}")
    print()
    print(truth["fault"].value_counts().to_string())
