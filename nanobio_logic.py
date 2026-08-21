import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

EPA_MCL_LIMITS = {
    "Lead": {"limit_mg_L": 0.015, "unit": "mg/L (15 µg/L)"},
    "Chromium": {"limit_mg_L": 0.100, "unit": "mg/L (100 µg/L)"},
    "Arsenic": {"limit_mg_L": 0.010, "unit": "mg/L (10 µg/L)"},
    "Heavy Metals": {"limit_mg_L": 0.050, "unit": "mg/L (50 µg/L)"}
}


def nanobio_ode_system(t, y, params):
    C, X, D, L = y  # Contaminant, Biomass, Active Nano, Leached Ions

    # Kinetic parameters
    k_nano = params['k_nano']
    u_max = params['u_max']
    K_s = params['K_s']
    Y = params['Y']
    K_d = params['K_d']
    alpha = params['alpha']
    k_deact = params['k_deact']
    k_leach = params['k_leach']

    # Contaminant removal rate
    r_nano = k_nano * C * D
    r_bio = (u_max * C / (K_s + C + 1e-6)) * (X / Y)
    dC_dt = - (r_nano + r_bio)

    # Microbial biomass growth rate (accounting for combined substrate and nano toxicity)
    dX_dt = ((u_max * C / (K_s + C + 1e-6)) - K_d - (alpha * (D + C))) * X

    # Nanoparticle deactivation & ion leaching rates
    dD_dt = - k_deact * D
    dL_dt = k_leach * D

    return [dC_dt, dX_dt, dD_dt, dL_dt]


def get_final_concentration(d_nano, c0, x0, t_max, params):
    """Integrates ODE system for a specific nanoparticle dosage and returns final contaminant concentration."""
    initial_conditions = [c0, x0, d_nano, 0.0]
    sol = solve_ivp(
        nanobio_ode_system,
        [0, t_max],
        initial_conditions,
        args=(params,),
        method='RK45'
    )
    return max(0.0, float(sol.y[0][-1]))


def calculate_min_required_dosage(c0, x0, t_max, params, target_mcl, max_dosage=500.0):
    """Calculates minimum nanoparticle dosage (mg/L) required to reach EPA MCL threshold within t_max."""
    # Check baseline concentration without nanoparticles
    c_zero_dose = get_final_concentration(0.0, c0, x0, t_max, params)
    if c_zero_dose <= target_mcl:
        return 0.0  # Biological bioremediation alone is sufficient

    # Check upper search bound
    c_max_dose = get_final_concentration(max_dosage, c0, x0, t_max, params)
    if c_max_dose > target_mcl:
        return None  # Cannot achieve compliance within t_max even at max bound

    def objective_func(d):
        return get_final_concentration(d, c0, x0, t_max, params) - target_mcl

    try:
        min_d = brentq(objective_func, 0.0, max_dosage, xtol=0.01)
        return round(float(min_d), 2)
    except Exception:
        return None


def calculate_required_contact_time(c0, x0, d0, params, target_mcl, max_search_time=1440.0):
    """Calculates required contact time in minutes to reach target MCL with current dosage d0."""
    initial_conditions = [c0, x0, d0, 0.0]

    sol_init = solve_ivp(nanobio_ode_system, [
                         0, max_search_time], initial_conditions, args=(params,), method='RK45')
    if float(sol_init.y[0][-1]) > target_mcl:
        return None

    def objective_func(t):
        s = solve_ivp(nanobio_ode_system, [
                      0, t], initial_conditions, args=(params,), method='RK45')
        return max(0.0, float(s.y[0][-1])) - target_mcl

    try:
        t_req = brentq(objective_func, 0.001, max_search_time, xtol=0.1)
        return round(float(t_req), 1)
    except Exception:
        return None


def evaluate_water_safety(contaminant: str, c_final: float, c0: float, x0: float, d0: float, t_max: float, params: dict) -> dict:
    for key, data in EPA_MCL_LIMITS.items():
        if key in contaminant:
            limit = data["limit_mg_L"]
            is_safe = c_final <= limit
            status = "SAFE (Compliant)" if is_safe else "UNSAFE (Exceeds Limit)"

            req_time = calculate_required_contact_time(
                c0, x0, d0, params, limit)
            min_dosage = calculate_min_required_dosage(
                c0, x0, t_max, params, limit)

            if is_safe:
                msg = f"Effluent ({c_final:.3f} mg/L) meets EPA limit ({limit} mg/L)."
            else:
                if min_dosage is not None:
                    msg = f"Effluent ({c_final:.3f} mg/L) exceeds EPA limit ({limit} mg/L). Increase dosage to ~{min_dosage} mg/L or extend contact time to ~{req_time} mins."
                else:
                    msg = f"CRITICAL: Cannot reach EPA compliance ({limit} mg/L) at current contact time ({t_max} min). Extend contact time or adjust operational parameters."

            return {
                "has_standard": True,
                "is_safe": is_safe,
                "status": status,
                "epa_mcl_mg_L": limit,
                "required_contact_time_min": req_time,
                "min_required_dosage_mg_L": min_dosage,
                "message": msg
            }

    return {
        "has_standard": False,
        "is_safe": True,
        "status": "N/A",
        "epa_mcl_mg_L": None,
        "required_contact_time_min": None,
        "min_required_dosage_mg_L": None,
        "message": "No strict EPA drinking water threshold defined for this compound."
    }


def simulate_nano_bioremediation(input_data: dict) -> dict:
    c0 = float(input_data.get('initial_concentration', 100.0))
    x0 = float(input_data.get('biomass_density', 500.0))
    d0 = float(input_data.get('nano_dosage', 20.0))
    t_max = float(input_data.get('contact_time', 60.0))
    uv = float(input_data.get('uv_intensity', 15.0))
    ph = float(input_data.get('ph', 7.0))
    contaminant = str(input_data.get('contaminant_type', 'Heavy Metals'))

    # Determine contaminant-specific reaction rates and optimal pH
    if "Lead" in contaminant or "Pb" in contaminant:
        k_nano_base, u_max_base, alpha_base, optimal_ph = 0.008, 0.015, 0.0015, 6.0
    elif "Chromium" in contaminant or "Cr" in contaminant:
        k_nano_base, u_max_base, alpha_base, optimal_ph = 0.004 * \
            (1.0 + 0.1 * uv), 0.005, 0.0040, 3.0
    elif "Arsenic" in contaminant or "As" in contaminant:
        k_nano_base, u_max_base, alpha_base, optimal_ph = 0.005, 0.010, 0.0025, 7.0
    elif "Heavy Metals" in contaminant:
        k_nano_base, u_max_base, alpha_base, optimal_ph = 0.005, 0.010, 0.0020, 6.5
    else:
        k_nano_base, u_max_base, alpha_base, optimal_ph = 0.003 * \
            (1.0 + 0.08 * uv), 0.040, 0.0005, 7.0

    ph_factor = np.exp(-0.3 * (ph - optimal_ph)**2)

    params = {
        'k_nano': k_nano_base * ph_factor,
        'u_max': u_max_base * ph_factor,
        'K_s': 25.0,
        'Y': 0.35,
        'K_d': 0.005,
        'alpha': alpha_base,
        'k_deact': 0.008,
        'k_leach': 0.0004
    }

    t_eval = np.linspace(0, t_max, 50)
    initial_conditions = [c0, x0, d0, 0.0]

    sol = solve_ivp(
        nanobio_ode_system,
        [0, t_max],
        initial_conditions,
        args=(params,),
        t_eval=t_eval,
        method='RK45'
    )

    c_final = max(0.0, float(sol.y[0][-1]))
    x_final = float(sol.y[1][-1])
    l_final = float(sol.y[3][-1])

    total_removal = ((c0 - c_final) / c0) * 100.0 if c0 > 0 else 0.0
    bio_viability = min(100.0, max(
        0.0, (x_final / x0) * 100.0)) if x0 > 0 else 0.0

    safety_eval = evaluate_water_safety(
        contaminant, c_final, c0, x0, d0, t_max, params)

    return {
        "time_series": {
            "time_min": np.round(sol.t, 1).tolist(),
            "contaminant_mg_L": np.round(sol.y[0], 3).tolist(),
            "biomass_mg_L": np.round(sol.y[1], 2).tolist(),
            "leached_ions_mg_L": np.round(sol.y[3], 3).tolist()
        },
        "simulation_results": {
            "effluent_concentration_mg_L": round(c_final, 3),
            "total_removal_efficiency_pct": round(total_removal, 2),
            "nano_phase_efficiency_pct": round(total_removal * 0.7, 2),
            "bio_phase_efficiency_pct": round(total_removal * 0.3, 2),
            "bio_viability_pct": round(bio_viability, 2),
            "nano_leaching_mg_L": round(l_final, 3),
            "safety_eval": safety_eval
        }
    }
