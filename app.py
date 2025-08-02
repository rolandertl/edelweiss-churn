import streamlit as st
import pandas as pd
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
import warnings
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

RELEVANT_GROUPS = [
    "Firmendaten Manager", "Website", "SEO", "Google Ads",
    "Postings", "Superkombis", "Social Media Werbeanzeigen"
]

# Reseller-Kundennummern (verwenden v1-Logik)
RESELLER_CUSTOMERS = [1902101, 1909143, 1903121, 1905146, 1911102]

def last_12_full_months(ref_date: pd.Timestamp):
    last_full = ref_date.replace(day=1) - pd.Timedelta(days=1)
    months = []
    for i in range(12):
        start = (last_full - relativedelta(months=i)).replace(day=1)
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        months.append((start, end))
    return list(reversed(months))

def map_group(row):
    cat = row['Produktkategorie']
    if cat != "Social Media":
        return cat
    prod = row['Produkt']
    postings = {
        "Social Media Postingpaket 12 Postings",
        "Social Media Postingpaket 24 Postings",
        "Social Media Postingpaket 52 Postings"
    }
    superk = {
        "Social Media SUPERKOMBI 12er", "Social Media SUPERKOMBI 12er (alt)",
        "Social Media SUPERKOMBI 24er", "Social Media SUPERKOMBI 24er (alt)",
        "Social Media SUPERKOMBI 52er", "Social Media SUPERKOMBI 52er (alt)"
    }
    ads = {"Social Media Werbeanzeigen Kampagnenbudget"}
    if prod in postings:
        return "Postings"
    if prod in superk:
        return "Superkombis"
    if prod in ads:
        return "Social Media Werbeanzeigen"
    return "Unbekannt"

def analyze_customer_journey(df: pd.DataFrame, grace_period_days: int = 90):
    """
    Analysiert Kundenverlauf und identifiziert True Churn vs. Reaktivierungen
    Reseller werden ausgeschlossen (verwenden v1-Logik)
    """
    # Reseller ausschließen für True Churn
    df_no_reseller = df[~df['Kundennummer'].isin(RESELLER_CUSTOMERS)].copy()
    
    # Kundenverlauf pro Kunde/Produkt aufbauen
    df_sorted = df_no_reseller.sort_values(['Kundennummer', 'ProductGroup', 'Beginn'])
    
    churn_events = []
    reactivations = []
    
    for (kunde, group), customer_df in df_sorted.groupby(['Kundennummer', 'ProductGroup']):
        customer_df = customer_df.reset_index(drop=True)
        
        for i, row in customer_df.iterrows():
            # Nur Verträge mit Enddatum betrachten
            if pd.isna(row['Ende']):
                continue
                
            end_date = row['Ende']
            
            # Prüfen ob es einen Folgevertrag gibt
            future_contracts = customer_df[
                (customer_df['Beginn'] > end_date) & 
                (customer_df.index > i)
            ]
            
            if len(future_contracts) > 0:
                # Nächster Vertrag gefunden
                next_start = future_contracts['Beginn'].min()
                gap_days = (next_start - end_date).days
                
                if gap_days <= grace_period_days:
                    # Reaktivierung (innerhalb Karenzzeit)
                    reactivations.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'Ende': end_date,
                        'NeuerBeginn': next_start,
                        'Luecke_Tage': gap_days,
                        'Typ': 'Reaktivierung'
                    })
                else:
                    # True Churn (Lücke zu groß)
                    churn_events.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'ChurnDatum': end_date,
                        'Typ': 'True Churn (lange Pause)'
                    })
            else:
                # Kein Folgevertrag = True Churn
                churn_events.append({
                    'Kundennummer': kunde,
                    'ProductGroup': group,
                    'ChurnDatum': end_date,
                    'Typ': 'True Churn (kein Folgevertrag)'
                })
    
    return pd.DataFrame(churn_events), pd.DataFrame(reactivations)

def calculate_yearly_churn(df: pd.DataFrame, churn_events: pd.DataFrame, start_year: int = 2020):
    """
    Berechnet Jahres-Churn Raten ab 2020 mit True Churn für Nicht-Reseller
    """
    today = pd.Timestamp.today()
    end_year = today.year
    yearly_records = []
    
    for year in range(start_year, end_year + 1):
        y_start = pd.Timestamp(f"{year}-01-01")
        y_end = today if year == end_year else pd.Timestamp(f"{year}-12-31")
        
        for group in RELEVANT_GROUPS:
            # Alle Kunden dieser Gruppe
            group_df = df[df['ProductGroup'] == group]
            
            if len(group_df) == 0:
                continue
            
            # Reseller und Nicht-Reseller trennen
            reseller_df = group_df[group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
            regular_df = group_df[~group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
            
            # Aktive Kunden zu Jahresbeginn
            active_customers = set()
            
            # Reguläre Kunden (kundenbasiert)
            for kunde, kunde_df in regular_df.groupby('Kundennummer'):
                kunde_active = kunde_df[
                    (kunde_df['Beginn'] < y_start) & 
                    ((kunde_df['Ende'].isna()) | (kunde_df['Ende'] >= y_start))
                ]
                if len(kunde_active) > 0:
                    active_customers.add(kunde)
            
            # Reseller (vertragsbasiert - wie v1)
            reseller_active = reseller_df[
                (reseller_df['Beginn'] < y_start) & 
                ((reseller_df['Ende'].isna()) | (reseller_df['Ende'] >= y_start))
            ]
            num_reseller_active = len(reseller_active)
            
            # Churn Events
            # True Churn für reguläre Kunden
            regular_churned = set(churn_events[
                (churn_events['ProductGroup'] == group) &
                (churn_events['ChurnDatum'] >= y_start) & 
                (churn_events['ChurnDatum'] <= y_end)
            ]['Kundennummer'].unique())
            
            # V1 Churn für Reseller
            reseller_churned = reseller_df[
                (reseller_df['Ende'] >= y_start) & 
                (reseller_df['Ende'] <= y_end)
            ]
            num_reseller_churned = len(reseller_churned)
            
            # Gesamte Churn Rate berechnen
            total_active = len(active_customers) + num_reseller_active
            total_churned = len(regular_churned) + num_reseller_churned
            
            churn_rate = (total_churned / total_active * 100) if total_active > 0 else 0.0
            
            yearly_records.append({
                'Jahr': year,
                'Gruppe': group,
                'AktiveKunden': len(active_customers),
                'AktiveReseller': num_reseller_active,
                'GesamtAktiv': total_active,
                'ChurnedKunden': len(regular_churned),
                'ChurnedReseller': num_reseller_churned,
                'GesamtChurned': total_churned,
                'JahresChurn (%)': round(churn_rate, 1)
            })
    
    return pd.DataFrame(yearly_records)

def calculate_current_year_churn(df: pd.DataFrame, churn_events: pd.DataFrame):
    """
    Berechnet aktuellen Jahres-Churn (laufendes Jahr)
    """
    today = pd.Timestamp.today()
    y_start = pd.Timestamp(f"{today.year}-01-01")
    
    current_churn = []
    
    for group in RELEVANT_GROUPS:
        group_df = df[df['ProductGroup'] == group]
        
        if len(group_df) == 0:
            current_churn.append({
                'Produktgruppe': group,
                'Aktive Kunden': 0,
                'Churned': 0,
                'Churn Rate (%)': 0.0
            })
            continue
        
        # Reseller und Nicht-Reseller trennen
        reseller_df = group_df[group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
        regular_df = group_df[~group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
        
        # Aktive Kunden zu Jahresbeginn
        active_customers = set()
        for kunde, kunde_df in regular_df.groupby('Kundennummer'):
            kunde_active = kunde_df[
                (kunde_df['Beginn'] < y_start) & 
                ((kunde_df['Ende'].isna()) | (kunde_df['Ende'] >= y_start))
            ]
            if len(kunde_active) > 0:
                active_customers.add(kunde)
        
        # Aktive Reseller
        reseller_active = len(reseller_df[
            (reseller_df['Beginn'] < y_start) & 
            ((reseller_df['Ende'].isna()) | (reseller_df['Ende'] >= y_start))
        ])
        
        # Churn Events dieses Jahr
        regular_churned = len(set(churn_events[
            (churn_events['ProductGroup'] == group) &
            (churn_events['ChurnDatum'] >= y_start)
        ]['Kundennummer'].unique()))
        
        reseller_churned = len(reseller_df[
            (reseller_df['Ende'] >= y_start)
        ])
        
        total_active = len(active_customers) + reseller_active
        total_churned = regular_churned + reseller_churned
        churn_rate = (total_churned / total_active * 100) if total_active > 0 else 0.0
        
        current_churn.append({
            'Produktgruppe': group,
            'Aktive Kunden': total_active,
            'Churned': total_churned,
            'Churn Rate (%)': round(churn_rate, 1)
        })
    
    return pd.DataFrame(current_churn)

def churn_auswerten_v2(df: pd.DataFrame, grace_period_days: int = 90):
    """
    Erweiterte Churn-Analyse mit True Churn Berechnung und Reseller-Behandlung
    """
    # Daten vorbereiten
    df = df[df['Abo'].astype(str).str.lower().isin(['ja','yes','true','1'])].copy()
    df['ProductGroup'] = df.apply(map_group, axis=1)
    df = df[df['ProductGroup'].isin(RELEVANT_GROUPS)]
    df['Beginn'] = pd.to_datetime(df['Beginn'], errors='coerce')
    df['Ende'] = pd.to_datetime(df['Ende'], errors='coerce')
    
    # Kundennummer zu int konvertieren
    df['Kundennummer'] = pd.to_numeric(df['Kundennummer'], errors='coerce').fillna(0).astype(int)

    # True Churn Analyse (ohne Reseller)
    churn_events, reactivations = analyze_customer_journey(df, grace_period_days)
    
    # Jahres-Churn berechnen
    yearly_churn = calculate_yearly_churn(df, churn_events, start_year=2020)
    current_year_churn = calculate_current_year_churn(df, churn_events)
    
    # Monatliche Daten für andere Auswertungen
    months = last_12_full_months(pd.Timestamp.today())
    v1_records = []
    for group, gdf in df.groupby('ProductGroup'):
        for start_ts, end_ts in months:
            active = gdf[(gdf['Beginn'] < start_ts) & ((gdf['Ende'].isna()) | (gdf['Ende'] >= start_ts))]
            churned = gdf[(gdf['Ende'] >= start_ts) & (gdf['Ende'] <= end_ts)]
            rate = (len(churned) / len(active) * 100) if len(active) > 0 else 0.0
            v1_records.append({
                'Monat': start_ts.strftime("%Y-%m"), 
                'Gruppe': group, 
                'OriginalChurn (%)': round(rate, 1)
            })
    df_v1 = pd.DataFrame(v1_records)
    df_v1_pivot = df_v1.pivot(index='Monat', columns='Gruppe', values='OriginalChurn (%)').fillna(0)

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
        'v1_pivot': df_v1_pivot,
        'reactivations': react_stats,
        'churn_events': churn_events,
        'reactivation_events': reactivations
    }

# Streamlit App
st.set_page_config(layout="wide")
st.title("🎯 Jahres-Churn Analyse v2 – EDELWEISS Digital")
st.markdown("**True Churn Analyse** mit Reseller-Berücksichtigung und Fokus auf Jahres-Churn")

# Sidebar für Einstellungen
st.sidebar.header("Einstellungen")
grace_period = st.sidebar.slider(
    "Karenzzeit für Reaktivierungen (Tage)", 
    min_value=30, 
    max_value=180, 
    value=90, 
    step=15,
    help="Kunden die innerhalb dieser Zeit das gleiche Produkt neu abschließen gelten nicht als Churn"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🏢 Reseller (verwenden v1-Logik)")
st.sidebar.markdown("""
- 1902101 - Onco
- 1909143 - Russmedia Verlag  
- 1903121 - Russmedia Digital
- 1905146 - Northlight
- 1911102 - Sam Solution
""")

file = st.file_uploader("Lade eine Excel-Datei hoch", type=["xlsx"])

# Berechnung nur starten wenn File vorhanden und Button gedrückt
if file:
    st.success("✅ Excel-Datei erfolgreich hochgeladen!")
    
    # Vorschau der Daten
    with st.expander("📋 Datenvorschau (erste 5 Zeilen)"):
        try:
            preview_df = pd.read_excel(file, nrows=5)
            st.dataframe(preview_df)
        except Exception as e:
            st.warning(f"Fehler beim Laden der Vorschau: {e}")
    
    st.markdown("---")
    
    # Zentraler Start-Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        start_calculation = st.button(
            "🚀 Churn-Analyse starten", 
            type="primary",
            use_container_width=True,
            help="Startet die Berechnung mit den aktuellen Einstellungen"
        )
    
    if start_calculation:
        # Progress und Spinner während Berechnung
        with st.spinner("🔄 Analysiere Churn-Daten..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Schritt 1: Daten laden
                status_text.text("📊 Lade Excel-Daten...")
                progress_bar.progress(10)
                df = pd.read_excel(file)
                
                # Schritt 2: Validierung
                status_text.text("✅ Validiere Datenspalten...")
                progress_bar.progress(20)
                required_cols = ['Abo', 'Produktkategorie', 'Produkt', 'Beginn', 'Ende', 'Kundennummer']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    st.error(f"❌ Fehlende Spalten: {', '.join(missing_cols)}")
                    st.stop()
                
                # Schritt 3: Datenanalyse
                status_text.text("🔍 Analysiere Kundenverlauf...")
                progress_bar.progress(40)
                results = churn_auswerten_v2(df, grace_period)
                
                # Schritt 4: Visualisierungen vorbereiten
                status_text.text("📈 Erstelle Visualisierungen...")
                progress_bar.progress(80)
                
                # Schritt 5: Fertig
                status_text.text("✨ Analyse abgeschlossen!")
                progress_bar.progress(100)
                
                # Kurz warten damit User den Abschluss sieht
                import time
                time.sleep(0.5)
                
                # Progress-Elemente entfernen
                progress_bar.empty()
                status_text.empty()

                # 🎯 HAUPTFOKUS: Aktueller Jahres-Churn
                st.header(f"🚨 Aktueller Jahres-Churn {pd.Timestamp.today().year}")
                
                # Metrics in Spalten
                current_churn = results['current_year_churn']
                if len(current_churn) > 0:
                    cols = st.columns(len(current_churn))
                    for i, (_, row) in enumerate(current_churn.iterrows()):
                        with cols[i]:
                            st.metric(
                                row['Produktgruppe'],
                                f"{row['Churn Rate (%)']}%",
                                delta=f"{row['Churned']}/{row['Aktive Kunden']} Kunden",
                                help=f"Churned: {row['Churned']} von {row['Aktive Kunden']} aktiven Kunden"
                            )
                    
                    # Detaillierte Tabelle
                    st.subheader("Aktuelle Jahres-Churn Details")
                    st.dataframe(current_churn, use_container_width=True)
                
                # 📈 Jahres-Verlauf seit 2020
                st.header("📈 Jahres-Churn Verlauf (seit 2020)")
                
                yearly_data = results['yearly_churn']
                if len(yearly_data) > 0:
                    # Pivot für Chart
                    yearly_pivot = yearly_data.pivot(index='Jahr', columns='Gruppe', values='JahresChurn (%)').fillna(0)
                    
                    # Interaktiver Line Chart
                    fig = go.Figure()
                    
                    colors = px.colors.qualitative.Set3
                    for i, gruppe in enumerate(yearly_pivot.columns):
                        fig.add_trace(go.Scatter(
                            x=yearly_pivot.index,
                            y=yearly_pivot[gruppe],
                            mode='lines+markers',
                            name=gruppe,
                            line=dict(color=colors[i % len(colors)], width=3),
                            marker=dict(size=8)
                        ))
                    
                    fig.update_layout(
                        title="Jahres-Churn Entwicklung nach Produktgruppen",
                        xaxis_title="Jahr",
                        yaxis_title="Churn Rate (%)",
                        hovermode='x unified',
                        height=500
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
# ─────────────────────────────────────────────────────────────
# ▶️ Waterfall-Diagramm zur Herleitung des Churn
# ─────────────────────────────────────────────────────────────
import plotly.graph_objects as go

# Annahme: df_summary existiert und hat schon aktive_vorjahr, aktive_aktuell, kuendigungen
aktive_vorjahr = int(df_summary["aktive_vorjahr"].sum())
kuendigungen   = int(df_summary["kuendigungen"].sum())
aktive_aktuell = int(df_summary["aktive_aktuell"].sum())
# Berechnung der neuen Abschlüsse, falls nicht separat vorliegen
neu            = aktive_aktuell + kuendigungen - aktive_vorjahr

def get_waterfall_chart(av, neu, kd, aa):
    fig = go.Figure(go.Waterfall(
        measure=["relative","relative","relative","total"],
        x=["Aktive Vorjahr","Neue Abschlüsse","Kündigungen","Aktive aktuell"],
        y=[av, neu, -kd, 0],
        text=[f"{av:,}", f"+{neu:,}", f"-{kd:,}", f"{aa:,}"],
        increasing={"marker":{"color":"#3CB371"}},
        decreasing={"marker":{"color":"#FF6347"}},
        totals={"marker":{"color":"#1E90FF"}},
    ))
    fig.update_layout(title="Churn-Herleitung (Waterfall)",
                      showlegend=False,
                      margin=dict(t=50,l=0,r=0,b=0))
    return fig

with st.container():
    st.subheader("🔄 Herleitung der Churn-Berechnung")
    col1, col2 = st.columns([1,1])
    with col1:
        st.markdown(
            f"**Aktive Vorjahr:** {aktive_vorjahr:,}  \n"
            f"**+ Neue Abschlüsse:** {neu:,}  \n"
            f"**− Kündigungen:** {kuendigungen:,}  \n"
            f"**= Aktive aktuell:** {aktive_aktuell:,}"
        )
    with col2:
        st.plotly_chart(get_waterfall_chart(
            aktive_vorjahr, neu, kuendigungen, aktive_aktuell
        ), use_container_width=True)
                    
                    # Jahres-Tabelle
                    st.subheader("Jahres-Churn Tabelle")
                    display_yearly = yearly_data.pivot(index='Jahr', columns='Gruppe', values='JahresChurn (%)').fillna(0)
                    st.dataframe(display_yearly, use_container_width=True)
                
                # Weitere Auswertungen in Tabs
                st.header("📊 Weitere Auswertungen")
                tab1, tab2, tab3, tab4 = st.tabs([
                    "🔄 Reaktivierungen", 
                    "📋 Monats-Churn (v1)",
                    "🔍 True Churn Events",
                    "ℹ️ Info & Statistiken"
                ])
                
                with tab1:
                    st.subheader("Reaktivierungs-Statistiken")
                    if len(results['reactivations']) > 0:
                        st.dataframe(results['reactivations'], use_container_width=True)
                        
                        if len(results['reactivation_events']) > 0:
                            st.subheader("Reaktivierungs-Details (Beispiele)")
                            st.dataframe(
                                results['reactivation_events'].head(20), 
                                use_container_width=True
                            )
                    else:
                        st.info("Keine Reaktivierungen in den Daten gefunden.")
                
                with tab2:
                    st.subheader("Monats-Churn (Original v1 Logik)")
                    st.dataframe(results['v1_pivot'], use_container_width=True)
                    if len(results['v1_pivot']) > 0:
                        st.line_chart(results['v1_pivot'])
                
                with tab3:
                    st.subheader("True Churn Events")
                    if len(results['churn_events']) > 0:
                        st.dataframe(results['churn_events'], use_container_width=True)
                        
                        # Verteilung nach Typ
                        churn_types = results['churn_events']['Typ'].value_counts()
                        st.subheader("Churn-Typen Verteilung")
                        st.bar_chart(churn_types)
                    else:
                        st.info("Keine True Churn Events gefunden.")
                
                with tab4:
                    st.subheader("📊 Statistiken & Informationen")
                    
                    total_customers = df['Kundennummer'].nunique()
                    reseller_count = df[df['Kundennummer'].isin(RESELLER_CUSTOMERS)]['Kundennummer'].nunique()
                    regular_customers = total_customers - reseller_count
                    total_reactivations = results['reactivations']['Anzahl Reaktivierungen'].sum() if len(results['reactivations']) > 0 else 0
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Gesamt Kunden", total_customers)
                    with col2:
                        st.metric("Reguläre Kunden", regular_customers)
                    with col3:
                        st.metric("Reseller", reseller_count)
                    with col4:
                        st.metric("Reaktivierungen", total_reactivations)
                    
                    st.markdown("---")
                    st.markdown("### 🔍 Methodik")
                    st.markdown(f"""
                    **True Churn Berechnung:**
                    - **Reguläre Kunden:** Berücksichtigung von Reaktivierungen (Karenzzeit: {grace_period} Tage)
                    - **Reseller:** Verwenden Original v1-Logik (vertragsbasiert)
                    - **Jahres-Churn:** Kombination beider Methoden für realistische Gesamtrate
                    
                    **Vorteile:**
                    - Realistische Churn-Raten durch Reaktivierungs-Berücksichtigung
                    - Korrekte Behandlung von Reseller-Geschäftsmodellen
                    - Fokus auf geschäftsrelevante Jahres-KPIs
                    """)

            except Exception as e:
                st.error(f"❌ Fehler beim Verarbeiten der Datei: {e}")
                st.exception(e)

else:
    st.info("👆 Bitte laden Sie eine Excel-Datei hoch, um mit der Analyse zu beginnen.")

# Footer
st.markdown("---")
st.markdown("*Churn-Analyse v2 with True Churn Logic & Reseller Handling*")
