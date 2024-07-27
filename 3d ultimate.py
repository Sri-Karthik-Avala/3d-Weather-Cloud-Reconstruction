import streamlit as st
import os
import shutil
import glob
from rasterio.features import shapes
import rasterio
import fiona
import geopandas as gpd
import pandas as pd
from rasterio.features import shapes
from datetime import datetime
from shapely.geometry import shape, mapping

def convert_radar_to_tiff(base_dir):
    folder_1_path = os.path.join(base_dir, "Input")
    folder_2_path = os.path.join(base_dir, "Tiff Files")
    folder_3_path = os.path.join(base_dir, "Geojson Files")
    folder_4_path = os.path.join(base_dir, "Output")

    # Create Folder 2, Folder 3, and Folder 4 if they don't exist
    for folder_path in [folder_2_path, folder_3_path, folder_4_path]:
        os.makedirs(folder_path, exist_ok=True)

    output_extension = ".tiff"

    for filename in os.listdir(folder_1_path):
        if filename:
            old_file_path = os.path.join(folder_1_path, filename)
            new_file_path = os.path.join(folder_2_path, os.path.splitext(filename)[0] + output_extension)

            shutil.copy(old_file_path, new_file_path)

    return folder_2_path

def raster_to_geojson(input_tif, output_geojson):
    with rasterio.open(input_tif) as src:
        image = src.read(1)
        transform = src.transform
        geoms = list(shapes(image, mask=None, transform=transform))

    feature_collection = {
        'type': 'FeatureCollection',
        'features': []
    }

    for geom, value in geoms:
        feature = {
            'type': 'Feature',
            'geometry': mapping(shape(geom)),
            'properties': {
                'reflectivity': float(value),
            }
        }
        feature_collection['features'].append(feature)

    with fiona.open(output_geojson, 'w', driver='GeoJSON', schema={'geometry': 'Polygon', 'properties': {'reflectivity': 'float'}}) as dst:
        dst.writerecords(feature_collection['features'])

def convert_tiff_to_geojson(base_dir, tiff_folder):
    input_folder = tiff_folder
    output_folder = os.path.join(base_dir, "Geojson Files")

    os.makedirs(output_folder, exist_ok=True)

    tif_files = glob.glob(os.path.join(input_folder, '*.tiff'))

    for tif_file in tif_files:
        geojson_file = os.path.join(output_folder, os.path.basename(tif_file).replace('.tiff', '.geojson'))
        raster_to_geojson(tif_file, geojson_file)

def stack_geojson_files(base_dir):
    geojson_folder = os.path.join(base_dir, "Geojson Files")
    output_geojson_path = os.path.join(base_dir, "Output", 'stacked.geojson')

    gdf_list = []
    layer_separation = 0.5
    file_counter = 0

    for filename in sorted(os.listdir(geojson_folder)):
        if filename.endswith(".geojson"):
            geojson_path = os.path.join(geojson_folder, filename)
            gdf = gpd.read_file(geojson_path)

            layer_name = os.path.splitext(filename)[0]
            date_str, time_str, _ = layer_name.split('_')
            timestamp_str = date_str + time_str
            timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')

            gdf['timestamp'] = timestamp
            gdf['geometry'] = gdf.geometry.centroid if gdf.geometry.type.iloc[0] != 'Point' else gdf.geometry
            gdf['longitude'] = gdf.geometry.x
            gdf['latitude'] = gdf.geometry.y
            gdf['altitude'] = gdf.shape[0] * layer_separation * 0.5

            gdf_list.append(gdf)
            file_counter += 1

            if file_counter % 36 == 0:
                file_counter = 0

    stacked_gdf = pd.concat(gdf_list, ignore_index=True)
    stacked_gdf.to_file(output_geojson_path, driver='GeoJSON')

# Streamlit App
def main():
    st.title("Radar Processing Streamlit App")
    st.write("This app converts radar files to TIFF, then to GeoJSON, and finally stacks the GeoJSON files.")

    base_dir = st.text_input("Enter the base path:", "")
    
    if st.button("Process"):
        if base_dir:
            st.write(f"Processing files in {base_dir}...")

            # Step 1: Convert Radar to TIFF
            tiff_folder = convert_radar_to_tiff(base_dir)
            st.write("Step 1: Radar files converted to TIFF.")

            # Step 2: Convert TIFF to GeoJSON
            convert_tiff_to_geojson(base_dir, tiff_folder)
            st.write("Step 2: TIFF files converted to GeoJSON.")

            # Step 3: Stack GeoJSON Files
            stack_geojson_files(base_dir)
            st.write("Step 3: GeoJSON files stacked.")

            st.success("Processing complete!")

if __name__ == "__main__":
    main()
