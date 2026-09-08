"""Physically-grounded emissions estimation module for AgniNetra.

Converts Fire Radiative Power (FRP) and temporal observation metrics into:
1. Fire Radiative Energy (FRE)
2. Biomass consumed (kg)
3. Atmospheric emissions (PM2.5 in kg, CO2 in tonnes)
"""

from __future__ import annotations

# Emission factors are literature-typical values by source category (Akagi et al. 2011 style EFs), not site-measured. Treat as estimates.
EMISSION_FACTORS: dict[str, dict[str, float]] = {
    "Agricultural": {
        "pm25": 0.0070,  # kg PM2.5 / kg biomass (crop residue burning)
        "co2": 1.515,    # kg CO2 / kg biomass
    },
    "Industrial": {
        "pm25": 0.0020,  # kg PM2.5 / kg biomass (flaring / combustion-like)
        "co2": 2.900,    # kg CO2 / kg biomass
    },
    "Wildfire": {
        "pm25": 0.0092,  # kg PM2.5 / kg biomass (forest / savanna average)
        "co2": 1.580,    # kg CO2 / kg biomass
    },
}

# Conservative duty cycle fraction: satellite samples ~1-2x/day; this avoids overclaiming continuous burning.
DUTY_CYCLE_FRACTION: float = 0.05

# Biomass combustion-rate coefficient: 0.368 kg/MJ (Wooster et al. 2005 FRP-to-biomass conversion factor).
COMBUSTION_RATE_COEFFICIENT: float = 0.368


def estimate_emissions(
    avg_frp: float | None,
    active_days: int | float | None,
    classification: str | None,
) -> dict:
    """Estimate biomass consumed, PM2.5, and CO2 emissions from FRP and persistence metrics.

    Parameters:
        avg_frp: Average Fire Radiative Power in MW.
        active_days: Distinct active detection days.
        classification: Thermal source classification ('Agricultural', 'Industrial', 'Wildfire').

    Returns:
        dict: {
            "fre_mj": float,
            "biomass_kg": float,
            "pm25_kg": float,
            "co2_tonnes": float,
            "assumptions": str
        }
    """
    assumptions = (
        "FRE estimated using avg FRP (MW) × active days × 86,400s × 0.05 duty cycle; "
        "biomass consumed via Wooster et al. 2005 (0.368 kg/MJ); "
        "emission factors are literature-typical values by source category "
        "(Akagi et al. 2011 style EFs), not site-measured. Treat as estimates."
    )

    if avg_frp is None or avg_frp <= 0:
        return {
            "fre_mj": 0.0,
            "biomass_kg": 0.0,
            "pm25_kg": 0.0,
            "co2_tonnes": 0.0,
            "assumptions": assumptions,
        }

    frp_mw = float(avg_frp)
    days = max(1.0, float(active_days if active_days is not None else 1.0))

    # FRE (MJ) = avg_frp (MW) * active_days * 86,400 s/day * duty_cycle_fraction
    fre_mj = frp_mw * days * 86400.0 * DUTY_CYCLE_FRACTION

    # Biomass consumed (kg) = FRE (MJ) * 0.368 kg/MJ (Wooster et al. 2005)
    biomass_kg = fre_mj * COMBUSTION_RATE_COEFFICIENT

    # Determine emission factors for category
    cat = (classification or "Agricultural").strip().capitalize()
    if cat not in EMISSION_FACTORS:
        if "flare" in cat.lower() or "indus" in cat.lower():
            cat = "Industrial"
        elif "wild" in cat.lower() or "forest" in cat.lower():
            cat = "Wildfire"
        else:
            cat = "Agricultural"

    ef = EMISSION_FACTORS[cat]

    pm25_kg = round(biomass_kg * ef["pm25"], 2)
    co2_tonnes = round((biomass_kg * ef["co2"]) / 1000.0, 3)

    return {
        "fre_mj": round(fre_mj, 2),
        "biomass_kg": round(biomass_kg, 2),
        "pm25_kg": pm25_kg,
        "co2_tonnes": co2_tonnes,
        "assumptions": assumptions,
    }
