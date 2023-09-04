import streamlit as st
from utils import *
import folium
from streamlit_folium import st_folium
import os 

st.title('🌞 Solar Explorer')

st.info('Bitte geben Sie Ihre Adressdaten ein, um die Solarpotentiale für Ihren Standort zu erkunden.')

# Initialize session state variables if not already initialized
if 'address_information_correct' not in st.session_state:
    st.session_state['address_information_correct'] = False
    
if 'solar_information_computed' not in st.session_state:
    st.session_state['solar_information_computed'] = False 

with st.expander("Adresseingabe", expanded=True):
    st.session_state.street = st.text_input("🏠 Straße & Hausnummer", value=st.session_state.get("street", "Preysingstraße 23"))
    st.session_state.city = st.text_input("🌆 Stadt", value=st.session_state.get("city", "Gauting"))
    st.session_state.zip_code = st.text_input("📮 Postleitzahl", value=st.session_state.get("zip_code", "82131"))
    st.session_state.country = st.text_input("🌍 Land", value=st.session_state.get("country", "Deutschland"))
    
    all_fields_filled = all([st.session_state.street, st.session_state.city, st.session_state.zip_code, st.session_state.country])
    
    if st.button('Submit', disabled=not all_fields_filled):
        st.session_state.lat, st.session_state.lon = get_location(st.session_state.street, st.session_state.city, st.session_state.zip_code, st.session_state.country)
        st.session_state.solardict = find_closest_building_insights(st.session_state.lat, st.session_state.lon, st.secrets["api_key"])
        st.session_state.address_information_correct = True
        st.session_state.solar_information_computed = False  

if st.session_state.address_information_correct and not st.session_state.solar_information_computed:

    with st.expander("Potentialmetriken", expanded=True): 

        st.markdown("##### Potentiale")

        max_array_panels_count = st.session_state.solardict["solarPotential"]['maxArrayPanelsCount']
        max_array_area_meters2 = st.session_state.solardict["solarPotential"]['maxArrayAreaMeters2']
        max_sunshine_hours_per_year = st.session_state.solardict["solarPotential"]['maxSunshineHoursPerYear']
        carbon_offset_factor_kg_per_mwh = st.session_state.solardict["solarPotential"]['carbonOffsetFactorKgPerMwh']
        panels_counts = [config['panelsCount'] for config in st.session_state.solardict["solarPotential"]['solarPanelConfigs']]
        yearly_energy_dc_kwh = [config['yearlyEnergyDcKwh'] for config in st.session_state.solardict["solarPotential"]['solarPanelConfigs']]
        max_panels_count = max(panels_counts)
        min_panels_count = min(panels_counts)
        max_yearly_energy_dc_kwh = int(max(yearly_energy_dc_kwh))
        min_yearly_energy_dc_kwh = int(min(yearly_energy_dc_kwh))

        col1, col2 = st.columns(2)
                        
        with col1:

            st.metric(label="🔢 Anzahl Solarpaneele", value = '{:,.0f}'.format(min_panels_count) + " - " + '{:,.0f}'.format(max_panels_count))
            st.metric(label="🌞 Jährliche Sonnenstunden", value = '{:,.0f}'.format(max_sunshine_hours_per_year).replace(',', '.') + " h")

        with col2: 
            st.metric(label="⚡ Energie-Einsparpotenzial", value = '{:,.0f}'.format(min_yearly_energy_dc_kwh).replace(',', '.') + " - " + '{:,.0f}'.format(max_yearly_energy_dc_kwh).replace(',', '.') + " kWh")
            st.metric(label="💨 CO2-Einsparpotenzial (Tonnen)", value = '{:,.0f}'.format(carbon_offset_factor_kg_per_mwh).replace(',', '.') + " T")


        st.markdown("##### Einsparpotenzialziel")

        col1, col2 = st.columns([2,1])

        with col1:
            desired_yearly_energy = st.slider('Jährliches Energieziel (kWh)', min_yearly_energy_dc_kwh, max_yearly_energy_dc_kwh)

            closest_energy = min(yearly_energy_dc_kwh, key=lambda x:abs(x-desired_yearly_energy))
            index = yearly_energy_dc_kwh.index(closest_energy)
            corresponding_panel_count = panels_counts[index]

        with col2:
            st.metric(label="Benötigte Anzahl an Solarpaneelen", value=corresponding_panel_count)


        st.markdown("##### Einsparpotenzial und Paneelanzahl")

        fig = plot_panels_vs_energy(st.session_state.solardict["solarPotential"]["solarPanelConfigs"], corresponding_panel_count)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'staticPlot': False, 'displaylogo': False, 'editable': False})




    with st.expander("Kartenansicht", expanded = True):
        tileurl = 'https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.png?access_token=' + str(st.secrets["token"])
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=19, tiles=tileurl, attr='Mapbox', max_zoom = 20)

        directory = os.path.join(os.getcwd(), f"{st.session_state.lat}_{st.session_state.lon}")

        options = ["📸 Luftbild", "🗺️ Oberflächenmodell", "🌞 Sonneneinstrahlung", "🏠 Gebäudemasken"]

        option_selected = st.selectbox("Select an option:", options)

        m = folium.Map(location=[st.session_state.lat,st.session_state.lon], zoom_start=18, tiles=tileurl, attr='Mapbox', max_zoom = 20)

        if not os.path.exists(directory):
            os.makedirs(directory)
            data_layers = get_data_layers(st.session_state.lat,st.session_state.lon, 100, 0.5, st.secrets["api_key"])
            get_geoTiff(data_layers, st.secrets["api_key"], directory)
            print(True)
            

        if option_selected == "🗺️ Oberflächenmodell":
            m = overlay_geotiff_dsm_on_folium_map(m, os.path.join(directory, "dsmUrl.tif"))
        elif option_selected == "🌞 Sonneneinstrahlung":
            m = overlay_geotiff_flux_on_folium_map(m, os.path.join(directory, "annualFluxUrl.tif"))
        elif option_selected ==  "🏠 Gebäudemasken":
            m = overlay_binary_mask_on_folium_map(m, os.path.join(directory, "maskUrl.tif"))
        elif option_selected == "📸 Luftbild":
            m = overlay_rgb_geotiff_on_folium_map(m, os.path.join(directory, "rgbUrl.tif"))

        m = add_location_to_map(m, st.session_state.solardict, corresponding_panel_count)
        st_data = st_folium(m, use_container_width=True)


    with st.expander("Solaranlagen-Angebot", expanded=True):
        # Display the matrix
        st.write("Hier ist eine Zusammenfassung Ihres Solaranlagen-Angebots:")

        # Define the metrics
        metrics = {
            "Gesamtkosten": ("💰", "20.000€"),
            "Jährliche Einsparungen": ("💲", "1.500€"),
            "Amortisationsdauer": ("📅", "13 Jahre"),
            "Anzahl installierbarer Solarpaneele": ("☀️", "20"),
        }

        # Display the metrics in a 2x2 matrix
        cols = st.columns(2)
        with cols[0]:
            st.metric(label=f"{metrics['Gesamtkosten'][0]} Gesamtkosten", value=metrics['Gesamtkosten'][1])
            st.metric(label=f"{metrics['Jährliche Einsparungen'][0]} Jährliche Einsparungen", value=metrics['Jährliche Einsparungen'][1])
        with cols[1]:
            st.metric(label=f"{metrics['Amortisationsdauer'][0]} Amortisationsdauer", value=metrics['Amortisationsdauer'][1])
            st.metric(label=f"{metrics['Anzahl installierbarer Solarpaneele'][0]} Anzahl installierbarer Solarpaneele", value=metrics['Anzahl installierbarer Solarpaneele'][1])

        # Display the button
        st.button("Vertrieb kontaktieren")

            

