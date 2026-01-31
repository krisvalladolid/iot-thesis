import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import time
from datetime import datetime

# --- Firebase setup ---
cred = credentials.Certificate("iot-final-project-989bf-firebase-adminsdk-fbsvc-0e708a642e.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://iot-final-project-989bf-default-rtdb.firebaseio.com/"
    })

# --- Streamlit Layout ---
st.set_page_config(page_title="Soil Moisture Analytics", layout="wide")
st.title("🌱 IoT Soil Moisture Analytics Dashboard")


# --- Function to fetch history data ---
def get_history():
    ref = db.reference("/sensorData/history")
    data = ref.get()
    if data:
        df = pd.DataFrame.from_dict(data, orient="index")

        # Convert timestamp string to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df = df.dropna(subset=["timestamp"])

        # Sort by time (newest first for display)
        df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
        return df
    return pd.DataFrame()


# --- Function to fetch current data ---
def get_current():
    ref = db.reference("/sensorData/current")
    return ref.get()


# --- Auto-refresh every 5 seconds ---
placeholder = st.empty()

while True:
    with placeholder.container():
        df = get_history()
        current = get_current()

        # --- Current Reading Section ---
        if current:
            st.subheader("📌 Latest Reading")
            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Soil Moisture", f"{current.get('moisturePercent', 'N/A')}%")
            col2.metric("Temperature", f"{current.get('temperature', 'N/A')}°C")
            col3.metric("Humidity", f"{current.get('humidity', 'N/A')}%")
            col4.metric("Status", current.get('status', 'N/A'))

            pump_status = "🟢 ON" if current.get('pump', False) else "🔴 OFF"
            col5.metric("Pump", pump_status)

            st.caption(f"Last Update: {current.get('timestamp', 'N/A')}")

        # --- Analytics Section ---
        if not df.empty:
            st.subheader("📊 Analytics Overview")

            # Key stats
            avg_moisture = df["moisturePercent"].mean()
            min_moisture = df["moisturePercent"].min()
            max_moisture = df["moisturePercent"].max()
            
            # Ensure temp/hum columns exist
            if "temperature" not in df.columns:
                df["temperature"] = pd.NA
            if "humidity" not in df.columns:
                df["humidity"] = pd.NA

            avg_temp = df["temperature"].mean() if not df["temperature"].isna().all() else 0
            avg_hum = df["humidity"].mean() if not df["humidity"].isna().all() else 0

            # Count actual pump activations (OFF -> ON transitions)
            df_sorted = df.sort_values("timestamp")  # Sort chronologically
            pump_activations = 0
            if "pump" in df.columns and len(df_sorted) > 1:
                # Count transitions from False to True
                pump_activations = ((df_sorted["pump"] == True) & (df_sorted["pump"].shift(1) == False)).sum()

            # Count total readings with pump ON
            pump_on_readings = df["pump"].sum() if "pump" in df.columns else 0

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Avg Moisture", f"{avg_moisture:.2f}%")
            
            # Show metrics (will show 0.00 or N/A logic if preferred, but here keeping consistent with code flow)
            if not df["temperature"].isna().all():
                c2.metric("Avg Temp", f"{avg_temp:.2f}°C")
                c3.metric("Avg Humidity", f"{avg_hum:.2f}%")
            else:
                c2.metric("Avg Temp", "N/A")
                c3.metric("Avg Humidity", "N/A")
                
            c4.metric("Max Moisture", f"{max_moisture}%")
            c5.metric("Pump Act.", f"{pump_activations}")

            # --- Time Series Chart ---
            st.subheader("📈 Trends Over Time")
            chart_df = df.sort_values("timestamp")  # Sort ascending for chart
            
            # Combined chart might be cluttered, let's do tabs
            tab1, tab2 = st.tabs(["Soil Moisture", "Temperature & Humidity"])
            
            with tab1:
                st.line_chart(chart_df.set_index("timestamp")["moisturePercent"])
            
            with tab2:
                import plotly.graph_objects as go

                def create_custom_chart(df, x_col, y_col, title, y_label, color, threshold=None):
                    fig = go.Figure()
                    
                    # Main Line
                    fig.add_trace(go.Scatter(
                        x=df[x_col], 
                        y=df[y_col],
                        mode='lines+markers',
                        name=y_label,
                        line=dict(color=color, width=3),
                        marker=dict(size=6, color=color)
                    ))

                    # Threshold Line
                    if threshold is not None:
                        fig.add_trace(go.Scatter(
                            x=[df[x_col].min(), df[x_col].max()],
                            y=[threshold, threshold],
                            mode='lines',
                            name='Limit',
                            line=dict(color='red', width=2, dash='dash'),
                            hoverinfo='none'
                        ))

                    fig.update_layout(
                        title=title,
                        xaxis_title="Time",
                        yaxis_title=y_label,
                        template="plotly_dark",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        height=350,
                        margin=dict(l=20, r=20, t=40, b=20),
                        showlegend=False
                    )
                    return fig

                fig_humidity = create_custom_chart(chart_df, "timestamp", "humidity", "Humidity Over Time", "Humidity (%)", "#0ea5e9")
                fig_temp = create_custom_chart(chart_df, "timestamp", "temperature", "Temperature Over Time", "Desc (°C)", "#ef4444")

                st.plotly_chart(fig_humidity, use_container_width=True)
                st.plotly_chart(fig_temp, use_container_width=True)

            # --- Status Distribution ---
            st.subheader("📝 Soil Status Breakdown")
            status_counts = df["status"].value_counts()
            st.bar_chart(status_counts)

            # --- Pump Activity ---
            st.subheader("⚙️ Pump Activity")
            col_a, col_b = st.columns(2)

            with col_a:
                pump_counts = df["pump"].value_counts()
                pump_labels = pump_counts.index.map({True: "ON", False: "OFF"})
                pump_df = pd.DataFrame({"Count": pump_counts.values}, index=pump_labels)
                st.bar_chart(pump_df)

            with col_b:
                pump_on_percent = (pump_on_readings / len(df)) * 100
                st.metric("Pump ON Time", f"{pump_on_percent:.1f}%")
                st.metric("Total Activations", pump_activations)
                st.metric("Total Readings", len(df))

            # --- Recent History Table ---
            st.subheader("🗂 Recent History (Last 20 Records)")
            cols_to_show = ["timestamp", "moisturePercent", "temperature", "humidity", "status", "pump"]
            
            display_df = df[cols_to_show].head(20).copy()
            display_df["pump"] = display_df["pump"].map({True: "ON", False: "OFF"})
            
            # Rename columns nicely
            col_map = {
                "timestamp": "Timestamp", 
                "moisturePercent": "Moisture %", 
                "status": "Status", 
                "pump": "Pump",
                "temperature": "Temp (°C)",
                "humidity": "Humidity (%)"
            }
            display_df = display_df.rename(columns=col_map)
            st.dataframe(display_df, use_container_width=True)

            # --- Download Data Option ---
            st.subheader("💾 Export Data")
            # Format dataframe for export
            export_df = df.copy()
            export_df["timestamp"] = export_df["timestamp"].dt.strftime('%Y-%m-%d %H:%M:%S')
            export_df["pump"] = export_df["pump"].map({True: "ON", False: "OFF"})
            
            # Select and rename all columns
            final_cols = ["timestamp", "moisturePercent", "temperature", "humidity", "status", "pump"]
            
            export_df = export_df[final_cols].rename(columns=col_map)

            csv = export_df.to_csv(index=False)
            st.download_button(
                label="Download Full History as CSV",
                data=csv,
                file_name=f"soil_moisture_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        else:
            st.warning("⚠️ No history data found in Firebase.")
            st.info("Make sure your ESP32 is connected and sending data to /sensorData/history")

        # --- Last refresh indicator ---
        st.caption(f"🔄 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    time.sleep(5)  # refresh every 5 seconds