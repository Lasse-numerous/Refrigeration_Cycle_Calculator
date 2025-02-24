"""
By: Alex Kalmbach

Description: This program provides thermodynamic information on the performance of a refrigeration cycle.
The user specifies the refrigerant they want to use as well as desired temperatures, pressures, and compressor
isentropic efficiency.
The CoolProp Library is used to get properties of the refrigerant at different points in the cycle, which are
ultimately used to calculate the heat removed, heat rejected, work input, and the cycle efficiency.

Sources:
[1] Thermodynamics An Engineering Approach (Cengel & Boles 8th Edition)
[2] Danfoss CoolSelector2

"""
import CoolProp.CoolProp as CP
from pint import UnitRegistry

# Initialize unit registry
ureg = UnitRegistry()
ureg.define("Rankine = 5/9 * kelvin = R")
ureg.define("lbm = pound")  # Define lbm explicitly
Q_ = ureg.Quantity

# Conversion Functions
def convert_to_si(property_name: str, value: float) -> float:
    conversions = {
        "T": Q_(value, "degF").to("kelvin").magnitude,
        "P": Q_(value, "psi").to("pascal").magnitude,
        "H": Q_(value, "Btu/lbm").to("J/kg").magnitude,
        "S": Q_(value, "Btu/(lbm*degF)").to("J/(kg*K)").magnitude,
        "M": Q_(value, "lbm/min").to("kg/s").magnitude,
        "D": Q_(value, "kg/m^3").to("lbm/ft^3").magnitude,
    }
    return conversions.get(property_name, value)

def convert_from_si(property_name: str, value: float) -> float:
    conversions = {
        "T": Q_(value, "kelvin").to("degF").magnitude,
        "P": Q_(value, "pascal").to("psi").magnitude,
        "H": Q_(value, "J/kg").to("Btu/lbm").magnitude,
        "S": Q_(value, "J/(kg*K)").to("Btu/(lbm*degF)").magnitude,
        "M": Q_(value, "kg/s").to("lbm/min").magnitude,
        "D": Q_(value, "kg/m^3").to("lbm/ft^3").magnitude,
        "Heat": Q_(value, "watt").to("BTU/hr").magnitude,  # Added Watts to BTU/hr conversion
    }
    return conversions.get(property_name, value)

def get_limited_input(prompt, min_val, max_val):
    """Prompt the user until they enter a valid number within the given range."""
    while True:
        try:
            value = float(input(prompt))
            if min_val <= value <= max_val:
                return value
        except ValueError:
            pass  # Ignore non-numeric input
        print(f"Invalid input. Please enter a number between {min_val} and {max_val}.")

# Refrigerant selection
refrigerant_list = ['R22', 'R134a', 'R32', 'R410A', 'R507A']

choice = int(input(f"Enter the list index of the refrigerant from the list {refrigerant_list}: "))
selected_refrigerant = refrigerant_list[choice]
print(f"You chose {selected_refrigerant}")

ref_state_list = ['ASHRAE','NBP','IIR']
while True:
    ref_state_choice = int(input(
        f"Enter the list index of the reference state to use for enthalpy and entropy from the list {ref_state_list}\n"
        f"Note: ASHRAE is used by Cengel Thermo books and the IRC Fluid Calc. Danfoss CoolSelector2 uses IIR\n"
        f"Reference State Choice: "
    ))
    if ref_state_choice in [0, 1, 2]:
        break
    print("Invalid choice. Please enter 0, 1, or 2.")

CP.set_reference_state(selected_refrigerant, ref_state_list[ref_state_choice])
print(f"You chose {ref_state_list[ref_state_choice]}")

# ============= EVAPORATOR INPUT LOOP =============
while True:
    evap_choice = input("Do you want to enter (1) low pressure in psia or (2) evaporating temperature in °F? Enter 1 or 2: ")
    if evap_choice not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2.")
        continue

    try:
        if evap_choice == '1':
            evap_pressure_psia = float(input("Enter the low pressure of the system in psia: "))
            low_pressure = convert_to_si("P", evap_pressure_psia)
            saturation_temp_evap = CP.PropsSI('T', 'P', low_pressure, 'Q', 1, selected_refrigerant)
        else:
            evap_temp_f = float(input("Enter the evaporator saturation temperature in °F: "))
            saturation_temp_evap = convert_to_si("T", evap_temp_f)
            low_pressure = CP.PropsSI('P', 'T', saturation_temp_evap, 'Q', 1, selected_refrigerant)

        # No explicit "evaporator must be less than something" check yet,
        # because we do not know the condenser side. We'll do that after we get the condenser side.
        break  # Evaporator side is valid, break the loop
    except ValueError:
        print("Invalid numeric input. Please try again.")
    except Exception as e:
        print(f"Error obtaining evaporator state: {e}. Please try again.")

# ============= CONDENSER INPUT LOOP =============
while True:
    cond_choice = input("Do you want to enter (1) high pressure in psia or (2) condensing temperature in °F? Enter 1 or 2: ")
    if cond_choice not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2.")
        continue

    try:
        if cond_choice == '1':
            cond_pressure_psia = float(input("Enter the high pressure of the system in psia: "))
            high_pressure = convert_to_si("P", cond_pressure_psia)
            saturation_temp_cond = CP.PropsSI('T', 'P', high_pressure, 'Q', 1, selected_refrigerant)
        else:
            cond_temp_f = float(input("Enter the condenser saturation temperature in °F: "))
            saturation_temp_cond = convert_to_si("T", cond_temp_f)
            high_pressure = CP.PropsSI('P', 'T', saturation_temp_cond, 'Q', 1, selected_refrigerant)

        # --- Validate: Condenser must be higher T and P than evaporator ---
        if saturation_temp_cond <= saturation_temp_evap:
            print("ERROR: Condenser saturation temperature must be greater than evaporator saturation temperature.")
            continue  # Stay in the loop, prompt user again

        if high_pressure <= low_pressure:
            print("ERROR: Condenser pressure must be greater than evaporator pressure.")
            continue

        # If we reach here, the condenser side is valid, so break
        break
    except ValueError:
        print("Invalid numeric input. Please try again.")
    except Exception as e:
        print(f"Error obtaining condenser state: {e}. Please try again.")

# Get validated superheat and subcooling values (0–30 °F)
superheat = convert_to_si("T", get_limited_input("Enter the amount of superheat in °F (0-30°F): ", 0, 30)) \
            - convert_to_si("T", 0) + 0.001
subcooling = convert_to_si("T", get_limited_input("Enter the amount of subcooling in °F (0-30°F): ", 0, 30)) \
             - convert_to_si("T", 0) + 0.001

# Compressor isentropic efficiency
while True:
    try:
        isentrop_eff = float(input("Enter compressor isentropic efficiency % (from 20 to 100): "))
        if 20 <= isentrop_eff <= 100:
            isentrop_eff /= 100
            break
        else:
            print("Invalid input. Please enter from 20 to 100.")
    except ValueError:
        print("Invalid numeric input. Please try again.")

# Mass flow rate
while True:
    try:
        mass_flow_rate_lb_min = float(input("Enter the mass flow rate of the system in lb/min: "))
        if mass_flow_rate_lb_min > 0:
            break
        else:
            print("Mass flow rate must be greater than 0.")
    except ValueError:
        print("Invalid numeric input. Please try again.")

mass_flow = convert_to_si("M", mass_flow_rate_lb_min)  # convert lb/min -> kg/s

# ------------------ STATE POINTS ------------------
# State 1 (Evaporator Exit)
state_1_pressure = low_pressure
state_1_temp = saturation_temp_evap + superheat
state_1_density = CP.PropsSI('D', 'P', state_1_pressure, 'T', state_1_temp, selected_refrigerant)
state_1_enthalpy = CP.PropsSI('H', 'P', state_1_pressure, 'T', state_1_temp, selected_refrigerant)
state_1_entropy = CP.PropsSI('S', 'P', state_1_pressure, 'T', state_1_temp, selected_refrigerant)

# State 2 (Compressor Exit, accounting for isentropic efficiency)
state_2_pressure = high_pressure
state_2_enthalpy_ideal = CP.PropsSI('H', 'P', state_2_pressure, 'S', state_1_entropy, selected_refrigerant)
state_2_enthalpy_actual = state_1_enthalpy + ((state_2_enthalpy_ideal - state_1_enthalpy) / isentrop_eff)
state_2_temp = CP.PropsSI('T', 'P', state_2_pressure, 'H', state_2_enthalpy_actual, selected_refrigerant)
state_2_density = CP.PropsSI('D', 'P', state_2_pressure, 'H', state_2_enthalpy_actual, selected_refrigerant)
state_2_entropy = CP.PropsSI('S', 'P', state_2_pressure, 'H', state_2_enthalpy_actual, selected_refrigerant)

# State 3 (Condenser Exit)
state_3_pressure = state_2_pressure
sat_liq_temp_cond = CP.PropsSI('T', 'P', state_3_pressure, 'Q', 0, selected_refrigerant)
state_3_temp = sat_liq_temp_cond - subcooling
state_3_density = CP.PropsSI('D', 'P', state_3_pressure, 'T', state_3_temp, selected_refrigerant)
state_3_enthalpy = CP.PropsSI('H', 'P', state_3_pressure, 'T', state_3_temp, selected_refrigerant)
state_3_entropy = CP.PropsSI('S', 'P', state_3_pressure, 'T', state_3_temp, selected_refrigerant)

# State 4 (Expansion Valve - Isenthalpic)
state_4_pressure = low_pressure
state_4_enthalpy = state_3_enthalpy
state_4_temp = CP.PropsSI('T', 'P', state_4_pressure, 'H', state_4_enthalpy, selected_refrigerant)
state_4_density = CP.PropsSI('D', 'P', state_4_pressure, 'H', state_4_enthalpy, selected_refrigerant)
state_4_entropy = CP.PropsSI('S', 'P', state_4_pressure, 'H', state_4_enthalpy, selected_refrigerant)
state_4_quality = CP.PropsSI('Q', 'P', state_4_pressure, 'H', state_4_enthalpy, selected_refrigerant)
if not (0 <= state_4_quality <= 1):
    print("Warning: Expansion valve output is not in two-phase region!")

# ------------------ PERFORMANCE ------------------
compressor_work = mass_flow * (state_2_enthalpy_actual - state_1_enthalpy)  # [W]
heat_removed    = mass_flow * (state_1_enthalpy - state_4_enthalpy)         # [W]
heat_rejected   = mass_flow * (state_2_enthalpy_actual - state_3_enthalpy)  # [W]
COP = heat_removed / compressor_work if compressor_work != 0 else 0.0

# ------------------ OUTPUT (IP Units) ------------------
print("\n--- Refrigeration Cycle Results (IP Units) ---")
states_data = [
    (state_1_temp, state_1_pressure, state_1_density, state_1_enthalpy, state_1_entropy),
    (state_2_temp, state_2_pressure, state_2_density, state_2_enthalpy_actual, state_2_entropy),
    (state_3_temp, state_3_pressure, state_3_density, state_3_enthalpy, state_3_entropy),
    (state_4_temp, state_4_pressure, state_4_density, state_4_enthalpy, state_4_entropy),
]

for i, (T, P, D, H, S) in enumerate(states_data, start=1):
    print(f"State {i} : "
          f"T = {convert_from_si('T', T):.1f} °F, "
          f"P = {convert_from_si('P', P):.1f} psia, "
          f"density = {convert_from_si('D', D):.2f} lbm/ft³, "
          f"h = {convert_from_si('H', H):.1f} BTU/lb, "
          f"s = {convert_from_si('S', S):.3f} BTU/(lbm·°F)")

# Convert performance metrics to IP
compressor_work_btu_hr = convert_from_si("Heat", compressor_work)
compressor_work_kw     = compressor_work / 1000
heat_removed_btu_hr    = convert_from_si("Heat", heat_removed)
heat_rejected_btu_hr   = convert_from_si("Heat", heat_rejected)
tons_of_refrigeration  = heat_removed_btu_hr / 12000
kw_per_ton             = compressor_work_kw / tons_of_refrigeration if tons_of_refrigeration > 0 else float('inf')

print("\n--- Performance Metrics (IP Units) ---")
print(f"Refrigerant: {selected_refrigerant}")
print(f"Refrigerant mass flow rate: {mass_flow_rate_lb_min:.2f} lbm/min")
print(f"Compressor Work Input: {compressor_work_btu_hr:.0f} BTU/hr ({compressor_work_kw:.1f} kW)")
print(f"Heat Removed (Cooling Capacity): {heat_removed_btu_hr:.0f} BTU/hr "
      f"({tons_of_refrigeration:.2f} Tons)")
print(f"Heat Rejected by Condenser: {heat_rejected_btu_hr:.0f} BTU/hr")
print(f"Coefficient of Performance (COP): {COP:.2f}")
print(f"kW per Ton: {kw_per_ton:.2f}")
print("Observe from the 1st Law of Thermo that the compressor work plus the heat absorbed in the evaporator equals "
      "the heat rejected by the condenser!")

