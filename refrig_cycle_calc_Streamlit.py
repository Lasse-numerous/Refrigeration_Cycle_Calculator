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

Date: 02/21/2025 (ver 2.0)
"""
import streamlit as st
import CoolProp.CoolProp as CP
from pint import UnitRegistry
import pandas as pd

ureg = UnitRegistry()
ureg.define("Rankine = 5/9 * kelvin = R")
ureg.define("lbm = pound")
Q_ = ureg.Quantity

def convert_to_si(property_name: str, value: float) -> float:
    """
    Convert from IP units to SI units for the given property.
    """
    conversions = {
        "T":  ureg.Quantity(value, "degF").to("kelvin").magnitude,   # °F -> K
        "P":  ureg.Quantity(value, "psi").to("pascal").magnitude,    # psia -> Pa
        "H":  ureg.Quantity(value, "Btu/lbm").to("J/kg").magnitude,  # BTU/lb -> J/kg
        "S":  ureg.Quantity(value, "Btu/(lbm*degF)").to("J/(kg*K)").magnitude,
        "M":  ureg.Quantity(value, "lbm/min").to("kg/s").magnitude,  # lb/min -> kg/s
    }
    return conversions.get(property_name, value)

def convert_from_si(property_name: str, value: float) -> float:
    """
    Convert from SI units back to IP units for printing.
    """
    conversions = {
        "T":    ureg.Quantity(value, "kelvin").to("degF").magnitude,
        "P":    ureg.Quantity(value, "pascal").to("psi").magnitude,
        "H":    ureg.Quantity(value, "J/kg").to("Btu/lbm").magnitude,
        "S":    ureg.Quantity(value, "J/(kg*K)").to("Btu/(lbm*degF)").magnitude,
        "D":    ureg.Quantity(value, "kg/m^3").to("lbm/ft^3").magnitude,
        "Heat": ureg.Quantity(value, "watt").to("BTU/hr").magnitude,  # W -> BTU/hr
    }
    return conversions.get(property_name, value)

def main():
    st.title("Refrigeration Cycle Simulator")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Input Parameters")
        
        # Refrigerant selection
        refrigerants = ["R22", "R134a", "R32", "R410A", "R507A"]
        refrigerant = st.selectbox("Select Refrigerant:", refrigerants)
        
        # Reference state
        ref_states = ["ASHRAE", "NBP", "IIR"]
        ref_state = st.selectbox("Select Reference State:", ref_states,
                                help="ASHRAE: Often used in textbooks\n"
                                     "NBP: Normal Boiling Point reference\n"
                                     "IIR: International Institute of Refrigeration")
        
        # Updated default values for evaporator
        evap_type = st.selectbox("Evaporator Input Type:", 
                                ["Temperature (°F)", "Pressure (psia)"])
        evap_value = st.number_input("Evaporator Value:", 
                                    value=40.0 if "Temperature" in evap_type else 85.0)
        
        # Updated default values for condenser
        cond_type = st.selectbox("Condenser Input Type:",
                                ["Temperature (°F)", "Pressure (psia)"])
        cond_value = st.number_input("Condenser Value:", 
                                    value=110.0 if "Temperature" in cond_type else 260.0)
        
        # Other parameters (with realistic defaults)
        superheat_F = st.number_input("Superheat (°F):", 
                                     min_value=0.0, max_value=30.0, value=10.0)
        subcooling_F = st.number_input("Subcooling (°F):", 
                                      min_value=0.0, max_value=30.0, value=10.0)
        isentropic_eff = st.number_input("Compressor Isentropic Efficiency (%):",
                                        min_value=20.0, max_value=100.0, value=70.0)
        mass_flow_lb_min = st.number_input("Mass Flow Rate (lb/min):",
                                          min_value=0.1, value=5.0)
    
    # Main content area
    st.image("pressure_enthalpy_diagram.png", caption="Fig 1: Refrigeration Cycle Pressure-Enthalpy Diagram")
    
    # Calculate button
    if st.button("Calculate"):
        try:
            # Set reference state
            CP.set_reference_state(refrigerant, ref_state)
            
            # Convert efficiency to fraction
            isentropic_eff_frac = isentropic_eff / 100.0
            
            # Evaporator side
            if "Pressure" in evap_type:
                low_pressure = convert_to_si("P", evap_value)
                sat_evap_T   = CP.PropsSI('T', 'P', low_pressure, 'Q', 1, refrigerant)
            else:
                sat_evap_T   = convert_to_si("T", evap_value)
                low_pressure = CP.PropsSI('P', 'T', sat_evap_T, 'Q', 1, refrigerant)

            # Condenser side
            if "Pressure" in cond_type:
                high_pressure = convert_to_si("P", cond_value)
                sat_cond_T    = CP.PropsSI('T', 'P', high_pressure, 'Q', 1, refrigerant)
            else:
                sat_cond_T    = convert_to_si("T", cond_value)
                high_pressure = CP.PropsSI('P', 'T', sat_cond_T, 'Q', 1, refrigerant)

            # Convert superheat & subcooling from °F to K
            superheat_K  = max(0.0001, superheat_F  * 5.0/9.0)
            subcooling_K = max(0.0001, subcooling_F * 5.0/9.0)
            mass_flow    = convert_to_si("M", mass_flow_lb_min)

            # STATE POINTS
            # 1: Evaporator Exit
            T1 = sat_evap_T + superheat_K
            H1 = CP.PropsSI('H', 'P', low_pressure, 'T', T1, refrigerant)
            S1 = CP.PropsSI('S', 'P', low_pressure, 'T', T1, refrigerant)
            D1 = CP.PropsSI('D', 'P', low_pressure, 'T', T1, refrigerant)

            # 2: Compressor Exit
            h2s_ideal = CP.PropsSI('H', 'P', high_pressure, 'S', S1, refrigerant)
            H2 = H1 + (h2s_ideal - H1) / isentropic_eff_frac
            T2 = CP.PropsSI('T', 'P', high_pressure, 'H', H2, refrigerant)
            S2 = CP.PropsSI('S', 'P', high_pressure, 'H', H2, refrigerant)
            D2 = CP.PropsSI('D', 'P', high_pressure, 'H', H2, refrigerant)

            # 3: Condenser Exit
            Tcond_sat = CP.PropsSI('T', 'P', high_pressure, 'Q', 0, refrigerant)
            T3 = Tcond_sat - subcooling_K
            H3 = CP.PropsSI('H', 'P', high_pressure, 'T', T3, refrigerant)
            S3 = CP.PropsSI('S', 'P', high_pressure, 'T', T3, refrigerant)
            D3 = CP.PropsSI('D', 'P', high_pressure, 'T', T3, refrigerant)

            # 4: Expansion Valve
            H4 = H3
            T4 = CP.PropsSI('T', 'P', low_pressure, 'H', H4, refrigerant)
            S4 = CP.PropsSI('S', 'P', low_pressure, 'H', H4, refrigerant)
            D4 = CP.PropsSI('D', 'P', low_pressure, 'H', H4, refrigerant)

            # PERFORMANCE
            compressor_work = mass_flow * (H2 - H1)
            heat_removed    = mass_flow * (H1 - H4)
            heat_rejected   = mass_flow * (H2 - H3)
            COP = heat_removed / compressor_work if compressor_work != 0 else 0.0

            # Convert to IP
            comp_btu_hr = convert_from_si("Heat", compressor_work)
            rem_btu_hr  = convert_from_si("Heat", heat_removed)
            rej_btu_hr  = convert_from_si("Heat", heat_rejected)

            tons_ref   = rem_btu_hr / 12000.0
            comp_kW    = compressor_work / 1000.0
            kw_per_ton = comp_kW / tons_ref if tons_ref > 0 else float('inf')

            # Convert state points to IP units
            T1_ip = convert_from_si("T", T1)
            P1_ip = convert_from_si("P", low_pressure)
            D1_ip = convert_from_si("D", D1)
            H1_ip = convert_from_si("H", H1)
            S1_ip = convert_from_si("S", S1)

            T2_ip = convert_from_si("T", T2)
            P2_ip = convert_from_si("P", high_pressure)
            D2_ip = convert_from_si("D", D2)
            H2_ip = convert_from_si("H", H2)
            S2_ip = convert_from_si("S", S2)

            T3_ip = convert_from_si("T", T3)
            P3_ip = convert_from_si("P", high_pressure)
            D3_ip = convert_from_si("D", D3)
            H3_ip = convert_from_si("H", H3)
            S3_ip = convert_from_si("S", S3)

            T4_ip = convert_from_si("T", T4)
            P4_ip = convert_from_si("P", low_pressure)
            D4_ip = convert_from_si("D", D4)
            H4_ip = convert_from_si("H", H4)
            S4_ip = convert_from_si("S", S4)

            # Display results using Streamlit
            st.header("Cycle Parameters")
            st.write(f"Refrigerant: {refrigerant}")
            st.write(f"Reference State: {ref_state}")
            st.write(f"Evaporator Input: {evap_value} ({evap_type})")
            st.write(f"Condenser Input: {cond_value} ({cond_type})")
            st.write(f"Superheat: {superheat_F:.1f} °F")
            st.write(f"Subcooling: {subcooling_F:.1f} °F")
            st.write(f"Isentropic Efficiency: {isentropic_eff:.1f}%")
            st.write(f"Mass Flow Rate: {mass_flow_lb_min:.2f} lb/min")
            
            # Create DataFrame for state points
            st.header("State Points")
            df = pd.DataFrame({
                "State": range(1, 5),
                "T(°F)": [T1_ip, T2_ip, T3_ip, T4_ip],
                "P(psia)": [P1_ip, P2_ip, P3_ip, P4_ip],
                "density(lbm/ft³)": [D1_ip, D2_ip, D3_ip, D4_ip],
                "h(BTU/lb)": [H1_ip, H2_ip, H3_ip, H4_ip],
                "s(BTU/lbm·°F)": [S1_ip, S2_ip, S3_ip, S4_ip]
            })
            st.dataframe(df)
            
            # Performance metrics
            st.header("Performance Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Compressor Work", f"{comp_btu_hr:,.0f} BTU/hr")
                st.metric("Heat Removed", f"{rem_btu_hr:,.0f} BTU/hr")
                st.metric("Heat Rejected", f"{rej_btu_hr:,.0f} BTU/hr")
            with col2:
                st.metric("Cooling Capacity", f"{tons_ref:.2f} Tons")
                st.metric("COP", f"{COP:.2f}")
                st.metric("kW per Ton", f"{kw_per_ton:.2f}")
                
        except Exception as e:
            st.error(f"Calculation Error: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("Developed in Python by Alex Kalmbach")

if __name__ == "__main__":
    main()
          st.metric("Heat Rejected", f"{rej_btu_hr:,.0f} BTU/hr")
            with col2:
                st.metric("Cooling Capacity", f"{tons_ref:.2f} Tons")
                st.metric("COP", f"{COP:.2f}")
                st.metric("kW per Ton", f"{kw_per_ton:.2f}")
                
        except Exception as e:
            st.error(f"Calculation Error: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("Developed in Python by Alex Kalmbach")

if __name__ == "__main__":
    main()
