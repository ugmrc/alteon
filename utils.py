from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import streamlit as st
import requests
from typing import Tuple, Union, Dict
import folium
import pandas as pd 
import plotly.graph_objects as go
import numpy as np
import rasterio
from folium import raster_layers
from pyproj import Transformer
import os 
import matplotlib.pyplot as plt

@st.cache_data
def get_location(street: str, city: str, zip_code: str, country: str) -> Union[Tuple[float, float], None]:
    geolocator = Nominatim(user_agent="GTA Lookup")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    location = geolocator.geocode(street + ", " + city + ", " + zip_code + ", " + country)
    
    if location is not None:
        lat = location.latitude
        lon = location.longitude
        return lat, lon
    else:
        return None
    


@st.cache_data
def find_closest_building_insights(lat: float, lon: float, key: str) -> Union[dict, None]:
    endpoint = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    params = {
        "location.latitude": lat,
        "location.longitude": lon,
        "requiredQuality": "HIGH",
        "key": key
    }
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code, response.text)
        return None


def add_location_to_map(_m: folium.Map, solar_potential: Dict, corresponding_panel_count) -> folium.Map:
    # Extract the center and bounding box coordinates from the solar_potential dictionary
    center = [solar_potential['center']['latitude'], solar_potential['center']['longitude']]
    sw = [solar_potential['boundingBox']['sw']['latitude'], solar_potential['boundingBox']['sw']['longitude']]
    ne = [solar_potential['boundingBox']['ne']['latitude'], solar_potential['boundingBox']['ne']['longitude']]
    
    # Define the color
    color = '#91d18b'

    folium.Rectangle(
        bounds=[sw, ne],
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0
    ).add_to(_m)

    # Add a white dot for each solar panel center
    solar_panels = solar_potential["solarPotential"]["solarPanels"][:corresponding_panel_count]
    print(solar_panels)
    for panel in solar_panels:
        panel_center = [panel['center']['latitude'], panel['center']['longitude']]
        folium.Circle(
            location=panel_center,
            radius=0.25,
            color = color,
            fill=True,
            fill_color="white"
        ).add_to(_m)
    
    return _m

@st.cache_data
def plot_panels_vs_energy(data, corresponding_panel_count):
    # Extract panelsCount and yearlyEnergyDcKwh from the data
    panels_count = [item['panelsCount'] for item in data]
    yearly_energy = [item['yearlyEnergyDcKwh'] for item in data]

    # Create a line plot with area under the curve colored
    fig = go.Figure(go.Scatter(
        x=panels_count,
        y=yearly_energy,
        mode='lines',
        fill='tozeroy',
        line=dict(color='#91D18B'),
    ))

    # Add a vertical line at corresponding_panel_count
    fig.add_vline(x=corresponding_panel_count, line=dict(color="#91D18B", width=3))

    # Update axis descriptions to German
    fig.update_xaxes(title=dict(text='Anzahl der Paneele', font=dict(color='#1B3C59')), tickfont=dict(color='#1B3C59'))
    fig.update_yaxes(title=dict(text='Jährliche Energie (kWh)', font=dict(color='#1B3C59')), tickfont=dict(color='#1B3C59'))

    # Update font to Inter
    fig.update_layout(font=dict(family='Inter', color='#1B3C59'), height=300, margin=dict(t=0, b=0, l=10, r=20))

    return fig

@st.cache_data
def get_geoTiff(data_layers: dict, api_key: str, directory: str) -> None:
    keys = ["dsmUrl", "rgbUrl",  "maskUrl", "annualFluxUrl"]
    for key in keys:
        url = f"{data_layers[key]}&key={api_key}"
        print(url)
        response = requests.get(url)
        response.raise_for_status()
        with open(os.path.join(directory, f'{key}.tif'), 'wb') as file:
            file.write(response.content)
            print(True)
            print(os.path.join(directory, f'{key}.tif'))

def overlay_geotiff_dsm_on_folium_map(m: folium.Map, file_path: str, nodata_value: int = -9999) -> folium.Map:
    with rasterio.open(file_path) as src:
        img = src.read(1)
        crs = src.crs
        bounds = src.bounds
    
    img = np.where(img == nodata_value, np.nan, img)
    img = (img - np.nanmin(img)) / (np.nanmax(img) - np.nanmin(img))
    img_rgb = plt.cm.viridis(img)[:, :, :3]
    img_rgb = (img_rgb * 255).astype(np.uint8)
    
    transformer = Transformer.from_crs(crs, 'epsg:4326')
    left, top = transformer.transform(bounds.left, bounds.top)
    right, bottom = transformer.transform(bounds.right, bounds.bottom)
    
    img_overlay = raster_layers.ImageOverlay(
        image=img_rgb,
        bounds=[[left, top], [right, bottom]],
    )
    
    img_overlay.add_to(m)
    return m

def overlay_geotiff_flux_on_folium_map(m: folium.Map, file_path: str, nodata_value: int = -9999) -> folium.Map:
    with rasterio.open(file_path) as src:
        img = src.read(1)
        crs = src.crs
        bounds = src.bounds
    
    img = np.where(img == nodata_value, np.nan, img)
    img = (img - np.nanmin(img)) / (np.nanmax(img) - np.nanmin(img))
    img_rgb = plt.cm.inferno(img)[:, :, :3]
    img_rgb = (img_rgb * 255).astype(np.uint8)
    
    transformer = Transformer.from_crs(crs, 'epsg:4326')
    left, top = transformer.transform(bounds.left, bounds.top)
    right, bottom = transformer.transform(bounds.right, bounds.bottom)
    
    img_overlay = raster_layers.ImageOverlay(
        image=img_rgb,
        bounds=[[left, top], [right, bottom]],
    )
    
    img_overlay.add_to(m)
    return m

def overlay_rgb_geotiff_on_folium_map(m: folium.Map, file_path: str) -> folium.Map:
    with rasterio.open(file_path) as src:
        img = src.read()
        img = np.transpose(img, (1, 2, 0))
        crs = src.crs
        bounds = src.bounds
    
    transformer = Transformer.from_crs(crs, 'epsg:4326')
    left, top = transformer.transform(bounds.left, bounds.top)
    right, bottom = transformer.transform(bounds.right, bounds.bottom)
    
    img_overlay = raster_layers.ImageOverlay(
        image=img,
        bounds=[[left, top], [right, bottom]],
    )
    
    img_overlay.add_to(m)
    return m

def overlay_binary_mask_on_folium_map(m: folium.Map, file_path: str) -> folium.Map:
    with rasterio.open(file_path) as src:
        img = src.read(1)
        crs = src.crs
        bounds = src.bounds
    
    transformer = Transformer.from_crs(crs, 'epsg:4326')
    left, top = transformer.transform(bounds.left, bounds.top)
    right, bottom = transformer.transform(bounds.right, bounds.bottom)
    
    rgba_img = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
    rgba_img[:, :, :3] = 255
    rgba_img[:, :, 3] = img * 255
    
    img_overlay = raster_layers.ImageOverlay(
        image=rgba_img,
        bounds=[[left, top], [right, bottom]],
    )
    
    img_overlay.add_to(m)
    return m

@st.cache_data
def get_data_layers(lat: float, lon: float, radius: float, pixel_size: float, key: str) -> Union[dict, None]:
    url = "https://solar.googleapis.com/v1/dataLayers:get"
    params = {
        'location.latitude': lat,
        'location.longitude': lon,
        'radiusMeters': radius,
        'view': 'FULL_LAYERS',
        'requiredQuality': 'HIGH',
        'pixelSizeMeters': pixel_size,
        'key': key,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code, response.text)
        return None