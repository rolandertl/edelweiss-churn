"""
EDELWEISS Digital - Churn Analytics Dashboard
Modern, interaktives Dashboard für Kundenabwanderungsanalyse
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
from churn_analytics import (
    RELEVANT_GROUPS, RESELLER_CUSTOMERS, RESELLER_NAMES,
    analyze_customer_journey, calculate_yearly_churn,
    calculate_waterfall_data, analyze_sales_performance,
    calculate_current_year_churn, map_group, last_12_full_months
)

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Moderne Farbpalette
COLORS = {
    'primary': '#6366F1',
    'success': '#10B981',
    'danger': '#EF4444',
    'warning': '#F59E0B',
    'info': '#3B82F6',
    'dark': '#1F2937',
    'gradient_start': '#667EEA',
    'gradient_end': '#764BA2'
}

def set_page_config():
    """Konfiguriert die Streamlit-Seite mit modernem Styling"""
    st.set_page_config(
        page_title="EDELWEISS Churn Analytics",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS für modernes Design
    st.markdown("""
    <style>
        .main {
            padding: 0rem 1rem;
        }
        
        h1 {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            margin-bottom: 2rem;
        }
        
        div[data-testid="metric-container"] {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border: 1px solid rgba(102, 126, 234, 0.2);
            padding: 1rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }
        
        div[data-testid="metric-container"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 0px 24px;
            background-color: rgba(102, 126, 234, 0.05);
            border-radius: 8px;
            border: 1px solid rgba(102, 126, 234, 0.2);
            font-weight: 600;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            border-radius: 8px;
            transition: all 0.3s;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px -5px rgba(102, 126, 234, 0.5);
        }
        
        .streamlit-expanderHeader {
            background: rgba(102, 126, 234, 0.05);
            border-radius: 8px;
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
        
        .stAlert {
            border-radius: 8px;
            border-left: 4px solid;
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        }
        
        .dataframe {
            border: 1px solid rgba(102, 126, 234, 0.2) !important;
            border-radius: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)

def create_gradient_header(title, subtitle=""):
    """Erstellt einen modernen Gradient-Header"""
    st.markdown(f"""
        <div style="padding: 2rem 0;">
            <h1 style="font-size: 3rem; margin-bottom: 0.5rem;">{title}</h1>
            <p style="font-size: 1.2rem; color: #64748B; font-weight: 500;">{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

def create_info_card(title, value, delta=None, color="primary"):
    """Erstellt eine moderne Info-Karte"""
    color_map = {
        'primary': '#6366F1',
        'success': '#10B981',
        'danger': '#EF4444',
        'warning': '#F59E0B'
    }
    
    delta_html = ""
    if delta:
        delta_color = "#10B981" if delta > 0 else "#EF4444"
        delta_symbol = "↑" if delta > 0 else "↓"
        delta_html = f'<p style="color: {delta_color}; font-size: 0.9rem; margin: 0;">{delta_symbol} {abs(delta)}%</p>'
    
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {color_map[color]}15 0%, {color_map[color]}05 100%);
            border-left: 4px solid {color_map[color]};
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        ">
            <p style="color: #64748B; font-size: 0.9rem; margin: 0;">{title}</p>
            <p style="color: #1F2937; font-size: 2rem; font-weight: 700; margin: 0.25rem 0;">{value}</p>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)

def process_data(df: pd.DataFrame, grace_period_days: int = 90, selected_sellers: list = None):
    """Verarbeitet die Daten und führt alle Analysen durch"""
    # Daten vorbereiten
    df = df[df['Abo'].astype(str).str.lower().isin(['ja','yes','true','1'])].copy()
    df['ProductGroup'] = df.apply(map_group, axis=1)
    df = df[df['ProductGroup'].isin(RELEVANT_GROUPS)]
    df['Beginn'] = pd.to_datetime(df['Beginn'], errors='coerce')
    df['Ende'] = pd.to_datetime(df['Ende'], errors='coerce')
    df['Kundennummer'] = pd.to_numeric(df['Kundennummer'], errors='coerce').fillna(0).astype(int)

    # Analysen durchführen
    churn_events, reactivations = analyze_customer_journey(df, grace_period_days)
    yearly_churn = calculate_yearly_churn(df, churn_events, start_year=2020)
    current_year_churn = calculate_current_year_churn(df, churn_events)
    waterfall_data = calculate_waterfall_data(df, churn_events, pd.Timestamp.today().year)
    sales_performance, sales_summary = analyze_sales_performance(df, churn_events, selected_sellers)
    
    # Monatliche Daten
    months = last_12_full_months(pd.Timestamp.today())
    monthly_records = []
    for group, gdf in df.groupby('ProductGroup'):
        for start_ts, end_ts in months:
            active = gdf[(gdf['Beginn'] < start_ts) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= start_ts))]
            churned = gdf[(gdf['Ende'] >= start_ts) & (gdf['Ende'] <= end_ts)]
            rate = (len(churned) / len(active) * 100) if len(active) > 0 else 0.0
            monthly_records.append({
                'Monat': start_ts.strftime("%Y-%m"),
                'Gruppe': group,
                'Churn (%)': round(rate, 1)
            })
    monthly_df = pd.DataFrame(monthly_records)
    monthly_pivot = monthly_df.pivot(index='Monat', columns='Gruppe', values='Churn (%)').fillna(0)

    # Reaktivierungs-Statistiken
    if len(reactivations) > 0:
        react_stats = reactivations.groupby('ProductGroup').agg({
            'Kundennummer': 'count',
            'Luecke_Tage': 'mean'
        }).round(1).reset_index()
        react_stats.columns = ['Produktgruppe', 'Anzahl Reaktivierungen', 'Ø Pause (Tage)']
    else:
        react_stats = pd.DataFrame(columns=['Produktgruppe', 'Anzahl Reaktivierungen', 'Ø Pause (Tage)'])

    return {
        'current_year_churn': current_year_churn,
        'yearly_churn': yearly_churn,
        'monthly_pivot': monthly_pivot,
        'reactivations': react_stats,
        'churn_events': churn_events,
        'reactivation_events': reactivations,
        'waterfall_data': waterfall_data,
        'sales_performance': sales_performance,
        'sales_summary': sales_summary,
        'df': df
    }

def create_waterfall_chart(waterfall_data, selected_group='Alle'):
    """Erstellt einen modernen Waterfall-Chart"""
    if selected_group == 'Alle':
        agg_data = waterfall_data.groupby('Gruppe').sum().sum()
        
        fig = go.Figure(go.Waterfall(
            name="Kundenentwicklung",
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=["Jahresstart", "Neukunden", "Verluste", "Aktueller Stand"],
            text=[f"+{int(agg_data['Start'])}", 
                  f"+{int(agg_data['Neukunden'])}", 
                  f"{int(agg_data['Verluste'])}", 
                  f"{int(agg_data['Ende'])}"],
            y=[agg_data['Start'], agg_data['Neukunden'], agg_data['Verluste'], agg_data['Ende']],
            connector={"line": {"color": "#E5E7EB", "width": 2}},
            increasing={"marker": {"color": "#10B981"}},
            decreasing={"marker": {"color": "#EF4444"}},
            totals={"marker": {"color": "#6366F1"}}
        ))
        
        title = f"Kundenentwicklung Gesamt - {pd.Timestamp.today().year}"
    else:
        group_data = waterfall_data[waterfall_data['Gruppe'] == selected_group].iloc[0]
        
        fig = go.Figure(go.Waterfall(
            name="Kundenentwicklung",
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=["Jahresstart", "Neukunden", "Verluste", "Aktueller Stand"],
            text=[f"+{int(group_data['Start'])}", 
                  f"+{int(group_data['Neukunden'])}", 
                  f"{int(group_data['Verluste'])}", 
                  f"{int(group_data['Ende'])}"],
            y=[group_data['Start'], group_data['Neukunden'], group_data['Verluste'], group_data['Ende']],
            connector={"line": {"color": "#E5E7EB", "width": 2}},
            increasing={"marker": {"color": "#10B981"}},
            decreasing={"marker": {"color": "#EF4444"}},
            totals={"marker": {"color": "#6366F1"}}
        ))
        
        title = f"Kundenentwicklung {selected_group} - {pd.Timestamp.today().year}"
    
    fig.update_layout(
        title=title,
        showlegend=False,
        height=500,
        font=dict(size=14),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hoverlabel=dict(
            bgcolor="white",
            font_size=14,
            font_family="Inter"
        )
    )
    
    return fig

def create_sales_performance_view(perf_data, summary, filter_type, selected_salesperson=None):
    """Erstellt die Verkäufer-Performance Ansicht"""
    if filter_type == "Einzelner Verkäufer" and selected_salesperson:
        seller_data = perf_data[perf_data['Verkäufer'] == selected_salesperson]
        
        if len(seller_data) > 0:
            total_active = seller_data['Aktive Kunden'].sum()
            total_new = seller_data['Neukunden'].sum()
            total_lost = seller_data['Verlorene Kunden'].sum()
            avg_churn = (total_lost / total_active * 100) if total_active > 0 else 0
            
            # Metrics in modernen Karten
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                create_info_card("Aktive Kunden", total_active, color="primary")
            with col2:
                create_info_card("Neukunden", f"+{total_new}", color="success")
            with col3:
                create_info_card("Verlorene Kunden", total_lost, color="danger")
            with col4:
                create_info_card("Churn Rate", f"{avg_churn:.1f}%", color="warning")
            
            st.markdown("### 📊 Performance nach Produktgruppe")
            
            # Moderner Bar Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='Aktive Kunden',
                x=seller_data['Produktgruppe'],
                y=seller_data['Aktive Kunden'],
                marker_color='#6366F1',
                text=seller_data['Aktive Kunden'],
                textposition='outside'
            ))
            fig.add_trace(go.Bar(
                name='Verlorene Kunden',
                x=seller_data['Produktgruppe'],
                y=seller_data['Verlorene Kunden'],
                marker_color='#EF4444',
                text=seller_data['Verlorene Kunden'],
                textposition='outside'
            ))
            fig.update_layout(
                barmode='group',
                height=400,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=14),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Detail-Tabelle
            st.dataframe(
                seller_data[['Produktgruppe', 'Aktive Kunden', 'Neukunden', 
                            'Verlorene Kunden', 'Churn Rate (%)']].style.format({
                    'Churn Rate (%)': '{:.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(f"Keine Daten für {selected_salesperson} gefunden")
    
    else:
        # Alle Verkäufer - Übersicht
        if len(summary) > 0:
            # Top/Bottom Performer Cards
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🏆 Top Performer")
                st.markdown("*Niedrigste Churn-Rate*")
                top5 = summary.head(5)
                for _, row in top5.iterrows():
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(90deg, #10B98115 0%, transparent 100%);
                        border-left: 3px solid #10B981;
                        padding: 0.5rem 1rem;
                        margin: 0.5rem 0;
                        border-radius: 4px;
                    ">
                        <strong>{row['Verkäufer']}</strong><br/>
                        <small>Churn: {row['Churn Rate (%)']}% | Aktiv: {row['Aktive Kunden']}</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("### ⚠️ Verbesserungspotential")
                st.markdown("*Höchste Churn-Rate*")
                bottom5 = summary.tail(5)
                for _, row in bottom5.iterrows():
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(90deg, #EF444415 0%, transparent 100%);
                        border-left: 3px solid #EF4444;
                        padding: 0.5rem 1rem;
                        margin: 0.5rem 0;
                        border-radius: 4px;
                    ">
                        <strong>{row['Verkäufer']}</strong><br/>
                        <small>Churn: {row['Churn Rate (%)']}% | Aktiv: {row['Aktive Kunden']}</small>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("### 📈 Churn-Rate Übersicht")
            
            # Nur relevante Verkäufer (min. 5 Kunden)
            relevant_sellers = summary[summary['Aktive Kunden'] >= 5].sort_values('Churn Rate (%)')
            
            if len(relevant_sellers) > 0:
                fig = go.Figure()
                
                # Farbskala basierend auf Performance
                colors = ['#10B981' if x < 10 else '#F59E0B' if x < 20 else '#EF4444' 
                         for x in relevant_sellers['Churn Rate (%)']]
                
                fig.add_trace(go.Bar(
                    x=relevant_sellers['Churn Rate (%)'],
                    y=relevant_sellers['Verkäufer'],
                    orientation='h',
                    marker_color=colors,
                    text=relevant_sellers['Churn Rate (%)'].apply(lambda x: f'{x:.1f}%'),
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>' +
                                  'Churn Rate: %{x:.1f}%<br>' +
                                  '<extra></extra>'
                ))
                
                fig.update_layout(
                    title="Verkäufer-Ranking (min. 5 aktive Kunden)",
                    xaxis_title="Churn Rate (%)",
                    yaxis_title="",
                    height=max(400, len(relevant_sellers) * 30),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=12),
                    margin=dict(l=150)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Performance Matrix Heatmap
            st.markdown("### 🎯 Performance-Matrix")
            
            pivot_churn = perf_data.pivot_table(
                index='Verkäufer',
                columns='Produktgruppe',
                values='Churn Rate (%)',
                fill_value=0
            )
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot_churn.values,
                x=pivot_churn.columns,
                y=pivot_churn.index,
                colorscale=[
                    [0, '#10B981'],
                    [0.5, '#F59E0B'],
                    [1, '#EF4444']
                ],
                text=pivot_churn.values,
                texttemplate='%{text:.1f}%',
                textfont={"size": 10},
                colorbar=dict(
                    title="Churn %",
                    tickmode="linear",
                    tick0=0,
                    dtick=10
                ),
                hoverongaps=False,
                hovertemplate='<b>%{y}</b><br>' +
                              '%{x}: %{z:.1f}%<br>' +
                              '<extra></extra>'
            ))
            
            fig.update_layout(
                title="Churn-Rate nach Verkäufer und Produktgruppe",
                height=max(400, len(pivot_churn.index) * 25),
                xaxis_title="Produktgruppe",
                yaxis_title="Verkäufer",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Export-Option
            with st.expander("📊 Daten exportieren"):
                csv = summary.to_csv(index=False)
                st.download_button(
                    label="📥 Verkäufer-Performance als CSV",
                    data=csv,
                    file_name=f"verkäufer_performance_{pd.Timestamp.today().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

# HAUPTAPP
def main():
    set_page_config()
    
    # Header
    create_gradient_header(
        "🎯 EDELWEISS Churn Analytics",
        "Intelligente Kundenabwanderungsanalyse mit KI-gestützten Insights"
    )
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Einstellungen")
        
        grace_period = st.slider(
            "🔄 Reaktivierungs-Karenzzeit",
            min_value=30,
            max_value=180,
            value=90,
            step=15,
            help="Tage bis ein Kunde als endgültig verloren gilt"
        )
        
        st.markdown("---")
        
        # Verkäufer-Filter aus GitHub laden
        st.markdown("### 👥 Verkäufer-Filter")
        
        selected_sellers = None
        available_sellers = []
        
        # Versuche verkaeufer.txt aus dem Repository zu laden
        try:
            import os
            if os.path.exists('verkaeufer.txt'):
                with open('verkaeufer.txt', 'r', encoding='utf-8') as f:
                    seller_content = f.read()
                    # Parse Verkäufer aus Datei (ignoriere Kommentare)
                    selected_sellers = [
                        line.strip() for line in seller_content.splitlines()
                        if line.strip() and not line.strip().startswith('#')
                    ]
                    st.success(f"✅ {len(selected_sellers)} Verkäufer aus verkaeufer.txt geladen")
            else:
                st.info("📝 Keine verkaeufer.txt gefunden - verwende alle Verkäufer")
                st.markdown("""
                **Tipp:** Erstelle eine `verkaeufer.txt` im Repository mit:
                ```
                # Relevante Verkäufer
                Max Mustermann
                Anna Schmidt
                # Externe (auskommentiert):
                # Peter External
                ```
                """)
        except Exception as e:
            st.warning(f"Fehler beim Lesen der verkaeufer.txt: {e}")
        
        st.markdown("---")
        
        # Reseller Info
        st.markdown("### 🏢 Spezialbehandlung: Reseller")
        st.info(
            "Folgende Reseller-Kunden werden bei der Churn-Berechnung "
            "gesondert behandelt:"
        )
        for kunde_nr, name in RESELLER_NAMES.items():
            st.markdown(f"• **{name}** ({kunde_nr})")
        
        st.markdown("---")
        
        # Info
        st.markdown("### 📊 Über diese Analyse")
        st.markdown("""
        Diese App analysiert Kundenabwanderung mit:
        - **Echte Kündigungen** vs. temporäre Pausen
        - **Jahres-Trends** seit 2020
        - **Verkäufer-Performance** Tracking
        - **Waterfall-Visualisierung** der Kundenbewegungen
        """)
    
    # File Upload
    file = st.file_uploader(
        "📁 Excel-Datei hochladen",
        type=["xlsx"],
        help="Laden Sie Ihre Kundendaten-Excel hier hoch"
    )
    
    if file:
        st.success("✅ Datei erfolgreich hochgeladen!")
        
        # Vorschau
        with st.expander("👀 Datenvorschau"):
            try:
                preview_df = pd.read_excel(file, nrows=5)
                st.dataframe(preview_df, use_container_width=True)
            except Exception as e:
                st.warning(f"Vorschau konnte nicht geladen werden: {e}")
        
        # Verkäufer aus Excel laden für Multiselect
        try:
            df_temp = pd.read_excel(file)
            if 'Zugewiesen an' in df_temp.columns:
                df_temp['Verkäufer'] = df_temp['Zugewiesen an'].fillna('Nicht zugewiesen').str.strip()
                available_sellers = sorted(df_temp['Verkäufer'].unique())
                
                # Multiselect wenn keine verkaeufer.txt geladen wurde
                if not selected_sellers and available_sellers:
                    st.markdown("### 🎯 Verkäufer auswählen")
                    
                    # Checkbox für schnelle Filterung
                    exclude_external = st.checkbox(
                        "Externe/Ehemalige automatisch ausschließen",
                        value=True,
                        help="Filtert Verkäufer mit 'extern', 'ehemalig', 'freelance', 'praktikant' im Namen"
                    )
                    
                    if exclude_external:
                        exclude_keywords = ['extern', 'ehemalig', 'freelance', 'praktikant', 'nicht zugewiesen']
                        default_selection = [
                            s for s in available_sellers 
                            if not any(keyword in s.lower() for keyword in exclude_keywords)
                        ]
                    else:
                        default_selection = available_sellers
                    
                    selected_sellers = st.multiselect(
                        "Wählen Sie die zu analysierenden Verkäufer:",
                        options=available_sellers,
                        default=default_selection,
                        help="Wählen Sie die Verkäufer aus, die in der Analyse berücksichtigt werden sollen"
                    )
                    
                    # Option zum Speichern der Auswahl
                    if st.button("💾 Auswahl als Standard speichern"):
                        try:
                            with open('verkaeufer.txt', 'w', encoding='utf-8') as f:
                                f.write("# Relevante Verkäufer für Churn-Analyse\n")
                                f.write("# Automatisch generiert\n\n")
                                for seller in selected_sellers:
                                    f.write(f"{seller}\n")
                                
                                # Nicht ausgewählte als Kommentar
                                f.write("\n# Ausgeschlossene Verkäufer:\n")
                                for seller in available_sellers:
                                    if seller not in selected_sellers:
                                        f.write(f"# {seller}\n")
                            
                            st.success("✅ Auswahl wurde in verkaeufer.txt gespeichert")
                        except Exception as e:
                            st.error(f"Fehler beim Speichern: {e}")
        except:
            pass
        
        # Start-Button - volle Breite ohne Spalten
        if st.button("🚀 Analyse starten", use_container_width=True, type="primary"):
            with st.spinner("🔄 Analysiere Daten..."):
                try:
                    # Daten laden und verarbeiten
                    df = pd.read_excel(file)
                    
                    # Validierung
                    required_cols = ['Abo', 'Produktkategorie', 'Produkt', 'Beginn', 'Ende', 'Kundennummer']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        st.error(f"❌ Fehlende Spalten: {', '.join(missing_cols)}")
                        st.stop()
                    
                    # Info über gefilterte Verkäufer
                    if selected_sellers:
                        st.info(f"🎯 Analyse für {len(selected_sellers)} ausgewählte Verkäufer")
                    
                    # Analyse durchführen
                    results = process_data(df, grace_period, selected_sellers)
                    
                    # HAUPTMETRICS
                    st.markdown("## 📊 Aktuelle Jahresübersicht")
                    
                    current_churn = results['current_year_churn']
                    if len(current_churn) > 0:
                        # Metrics Cards
                        cols = st.columns(len(current_churn))
                        for i, (_, row) in enumerate(current_churn.iterrows()):
                            with cols[i]:
                                color = "success" if row['Churn Rate (%)'] < 10 else "warning" if row['Churn Rate (%)'] < 20 else "danger"
                                st.metric(
                                    row['Produktgruppe'],
                                    f"{row['Churn Rate (%)']}%",
                                    delta=f"{row['Verluste']} von {row['Aktive Kunden']}",
                                    delta_color="inverse"
                                )
                    
                    # TABS für verschiedene Analysen
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📈 Trends",
                        "💧 Waterfall",
                        "👥 Verkäufer",
                        "🔄 Reaktivierungen",
                        "📊 Details"
                    ])
                    
                    with tab1:
                        st.markdown("### 📈 Jahres-Trend Analyse")
                        
                        yearly_data = results['yearly_churn']
                        if len(yearly_data) > 0:
                            yearly_pivot = yearly_data.pivot(index='Jahr', columns='Gruppe', values='JahresChurn (%)').fillna(0)
                            
                            # Tabelle über dem Chart
                            st.markdown("#### 📊 Jahres-Churn Übersicht")
                            
                            # Formatierte Tabelle mit Farbcodierung
                            styled_pivot = yearly_pivot.style.format('{:.1f}%').background_gradient(
                                cmap='RdYlGn_r',
                                vmin=0,
                                vmax=30,
                                axis=None
                            ).set_properties(**{
                                'font-weight': 'bold',
                                'text-align': 'center'
                            })
                            
                            st.dataframe(styled_pivot, use_container_width=True)
                            
                            # Zusammenfassungs-Metriken
                            st.markdown("#### 📈 Trend-Entwicklung")
                            
                            fig = go.Figure()
                            colors = px.colors.qualitative.Set2
                            
                            for i, gruppe in enumerate(yearly_pivot.columns):
                                fig.add_trace(go.Scatter(
                                    x=yearly_pivot.index,
                                    y=yearly_pivot[gruppe],
                                    mode='lines+markers',
                                    name=gruppe,
                                    line=dict(color=colors[i % len(colors)], width=3),
                                    marker=dict(size=10),
                                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                                  'Jahr: %{x}<br>' +
                                                  'Churn: %{y:.1f}%<br>' +
                                                  '<extra></extra>'
                                ))
                            
                            fig.update_layout(
                                title="Churn-Entwicklung 2020 bis heute",
                                xaxis_title="Jahr",
                                yaxis_title="Churn Rate (%)",
                                hovermode='x unified',
                                height=500,
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(size=14),
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=-0.2,
                                    xanchor="center",
                                    x=0.5
                                )
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Zusätzliche Insights unter dem Chart
                            with st.expander("🔍 Detaillierte Analyse"):
                                # Durchschnittlicher Churn pro Gruppe
                                avg_churn = yearly_pivot.mean().round(1)
                                trend_data = []
                                
                                for gruppe in yearly_pivot.columns:
                                    values = yearly_pivot[gruppe]
                                    first_year = values.iloc[0]
                                    last_year = values.iloc[-1]
                                    change = last_year - first_year
                                    trend = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                                    
                                    trend_data.append({
                                        'Produktgruppe': gruppe,
                                        'Ø Churn': f"{avg_churn[gruppe]}%",
                                        f'{values.index[0]}': f"{first_year}%",
                                        f'{values.index[-1]}': f"{last_year}%",
                                        'Veränderung': f"{change:+.1f}%",
                                        'Trend': trend
                                    })
                                
                                trend_df = pd.DataFrame(trend_data)
                                st.dataframe(
                                    trend_df.style.format(precision=1),
                                    use_container_width=True,
                                    hide_index=True
                                )
                    
                    with tab2:
                        st.markdown("### 💧 Kundenentwicklung Waterfall")
                        
                        waterfall = results['waterfall_data']
                        if len(waterfall) > 0:
                            selected_group = st.selectbox(
                                "Produktgruppe auswählen:",
                                options=['Alle'] + list(waterfall['Gruppe'].unique())
                            )
                            
                            fig = create_waterfall_chart(waterfall, selected_group)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Detail-Tabelle
                            with st.expander("📋 Waterfall Details"):
                                st.dataframe(waterfall, use_container_width=True, hide_index=True)
                    
                    with tab3:
                        st.markdown("### 👥 Verkäufer-Performance")
                        
                        if selected_sellers:
                            st.success(f"✅ Zeige Daten für {len(selected_sellers)} ausgewählte Verkäufer")
                        
                        if 'Zugewiesen an' in df.columns:
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                filter_type = st.radio(
                                    "Ansicht:",
                                    ["Alle Verkäufer", "Einzelner Verkäufer"]
                                )
                            
                            with col2:
                                if filter_type == "Einzelner Verkäufer":
                                    # Nur ausgewählte Verkäufer zur Auswahl
                                    seller_options = selected_sellers if selected_sellers else sorted(df['Verkäufer'].unique())
                                    selected_salesperson = st.selectbox(
                                        "Verkäufer:",
                                        options=seller_options
                                    )
                                else:
                                    selected_salesperson = None
                            
                            create_sales_performance_view(
                                results['sales_performance'],
                                results['sales_summary'],
                                filter_type,
                                selected_salesperson
                            )
                        else:
                            st.warning("⚠️ Spalte 'Zugewiesen an' nicht gefunden - Verkäufer-Analyse nicht möglich")
                    
                    with tab4:
                        st.markdown("### 🔄 Reaktivierungen")
                        
                        if len(results['reactivations']) > 0:
                            st.dataframe(
                                results['reactivations'].style.format({
                                    'Ø Pause (Tage)': '{:.0f}'
                                }),
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("Keine Reaktivierungen gefunden")
                    
                    with tab5:
                        st.markdown("### 📊 Detailanalysen")
                        
                        # Monatlicher Churn
                        st.markdown("#### Monatlicher Churn (letzte 12 Monate)")
                        st.dataframe(
                            results['monthly_pivot'].style.format('{:.1f}%'),
                            use_container_width=True
                        )
                        
                        # Statistiken
                        st.markdown("#### Gesamtstatistiken")
                        total_customers = df['Kundennummer'].nunique()
                        reseller_count = len([k for k in df['Kundennummer'].unique() if k in RESELLER_CUSTOMERS])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Gesamt Kunden", total_customers)
                        with col2:
                            st.metric("Reguläre Kunden", total_customers - reseller_count)
                        with col3:
                            st.metric("Reseller", reseller_count)
                
                except Exception as e:
                    st.error(f"❌ Fehler bei der Analyse: {e}")
                    st.exception(e)
    else:
        # Welcome Screen
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            margin: 2rem 0;
        ">
            <h2>👋 Willkommen bei EDELWEISS Churn Analytics</h2>
            <p style="font-size: 1.1rem; color: #64748B; margin: 1rem 0;">
                Laden Sie Ihre Excel-Datei hoch, um mit der intelligenten Kundenanalyse zu beginnen.
            </p>
            <p style="color: #94A3B8;">
                Benötigte Spalten: Abo, Produktkategorie, Produkt, Beginn, Ende, Kundennummer, Zugewiesen an
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Beispiel-Verkäuferliste anzeigen
        with st.expander("📝 Beispiel: Verkäufer-Liste Format"):
            st.markdown("""
            Erstellen Sie eine `verkaeufer.txt` Datei mit folgendem Format:
            ```
            # Relevante Verkäufer für Churn-Analyse
            # Jeden Namen in eine neue Zeile
            # Zeilen mit # werden ignoriert
            
            Max Mustermann
            Anna Schmidt
            Thomas Weber
            Julia Fischer
            
            # Externe/Ehemalige (auskommentiert):
            # Peter External
            # Klaus Ehemalig
            ```
            """)

if __name__ == "__main__":
    main()
