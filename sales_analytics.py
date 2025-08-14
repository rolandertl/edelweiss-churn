"""
Sales Analytics Module
Erweiterte Verkäufer-Performance Analyse mit multiplen KPIs
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Mindest-Schwellenwert für Verkäufer-Bewertung
MIN_ACTIVE_CUSTOMERS = 50

def calculate_customer_lifetime(df: pd.DataFrame, verkäufer: str) -> float:
    """
    Berechnet die durchschnittliche Kundenbindungsdauer eines Verkäufers
    """
    v_df = df[df['Verkäufer'] == verkäufer].copy()
    
    # Berechne Vertragsdauer für jeden Kunden
    v_df['Vertragsdauer'] = pd.NaT
    
    # Für beendete Verträge
    mask_ended = v_df['Ende'].notna()
    v_df.loc[mask_ended, 'Vertragsdauer'] = (
        v_df.loc[mask_ended, 'Ende'] - v_df.loc[mask_ended, 'Beginn']
    ).dt.days
    
    # Für laufende Verträge
    mask_active = v_df['Ende'].isna()
    v_df.loc[mask_active, 'Vertragsdauer'] = (
        pd.Timestamp.today() - v_df.loc[mask_active, 'Beginn']
    ).dt.days
    
    # Durchschnitt in Monaten
    avg_days = v_df.groupby('Kundennummer')['Vertragsdauer'].mean().mean()
    return round(avg_days / 30.44, 1) if not pd.isna(avg_days) else 0

def calculate_reactivation_rate(df: pd.DataFrame, verkäufer: str, reactivations_df: pd.DataFrame) -> float:
    """
    Berechnet die Reaktivierungsquote eines Verkäufers
    """
    if len(reactivations_df) == 0:
        return 0.0
    
    # Kunden des Verkäufers
    v_customers = df[df['Verkäufer'] == verkäufer]['Kundennummer'].unique()
    
    # Reaktivierungen dieses Verkäufers
    v_reactivations = reactivations_df[
        reactivations_df['Kundennummer'].isin(v_customers)
    ]['Kundennummer'].nunique()
    
    # Gesamte gekündigte Kunden
    v_churned = df[
        (df['Verkäufer'] == verkäufer) & 
        (df['Ende'].notna())
    ]['Kundennummer'].nunique()
    
    if v_churned == 0:
        return 0.0
    
    return round((v_reactivations / v_churned) * 100, 1)

def calculate_upselling_rate(df: pd.DataFrame, verkäufer: str) -> float:
    """
    Berechnet die Upselling-Rate (Kunden mit mehreren Produkten)
    """
    v_df = df[df['Verkäufer'] == verkäufer]
    
    # Zähle Produkte pro Kunde
    products_per_customer = v_df.groupby('Kundennummer')['ProductGroup'].nunique()
    
    # Kunden mit mehr als einem Produkt
    multi_product_customers = (products_per_customer > 1).sum()
    total_customers = len(products_per_customer)
    
    if total_customers == 0:
        return 0.0
    
    return round((multi_product_customers / total_customers) * 100, 1)

def calculate_customer_value(df: pd.DataFrame, verkäufer: str) -> dict:
    """
    Berechnet Customer Lifetime Value Metriken
    Hinweis: Ohne Preisdaten verwenden wir Proxy-Metriken
    """
    v_df = df[df['Verkäufer'] == verkäufer]
    
    # Proxy-Metriken für CLV
    metrics = {
        'avg_products_per_customer': round(
            v_df.groupby('Kundennummer')['ProductGroup'].nunique().mean(), 2
        ),
        'premium_product_rate': 0.0,  # Placeholder für Premium-Produkte
        'total_contract_months': 0
    }
    
    # Berechne Gesamt-Vertragsmonate
    for _, row in v_df.iterrows():
        if pd.notna(row['Ende']):
            months = (row['Ende'] - row['Beginn']).days / 30.44
        else:
            months = (pd.Timestamp.today() - row['Beginn']).days / 30.44
        metrics['total_contract_months'] += months
    
    metrics['total_contract_months'] = round(metrics['total_contract_months'], 0)
    
    # Premium-Produkte identifizieren (z.B. Superkombis als Premium)
    if 'Superkombis' in v_df['ProductGroup'].values:
        premium_customers = v_df[v_df['ProductGroup'] == 'Superkombis']['Kundennummer'].nunique()
        total_customers = v_df['Kundennummer'].nunique()
        metrics['premium_product_rate'] = round(
            (premium_customers / total_customers * 100) if total_customers > 0 else 0, 1
        )
    
    return metrics

def analyze_sales_performance_extended(
    df: pd.DataFrame, 
    churn_events: pd.DataFrame,
    reactivations: pd.DataFrame,
    selected_sellers: list = None
) -> tuple:
    """
    Erweiterte Verkäufer-Performance Analyse mit multiplen KPIs
    
    Returns:
        detailed_performance: DataFrame mit allen KPIs pro Verkäufer
        summary: Zusammenfassung mit Ranking
        insights: Zusätzliche Insights und Empfehlungen
    """
    # Vorbereitung
    if 'Zugewiesen an' not in df.columns:
        return pd.DataFrame(), pd.DataFrame(), {}
    
    df['Verkäufer'] = df['Zugewiesen an'].fillna('Nicht zugewiesen').str.strip()
    
    # Filter auf ausgewählte Verkäufer
    if selected_sellers:
        df = df[df['Verkäufer'].isin(selected_sellers)]
    
    current_year = pd.Timestamp.today().year
    y_start = pd.Timestamp(f"{current_year}-01-01")
    
    performance_data = []
    
    for verkäufer in df['Verkäufer'].unique():
        v_df = df[df['Verkäufer'] == verkäufer]
        
        # Basis-Metriken
        active = v_df[
            (v_df['Beginn'] < y_start) & 
            ((v_df['Ende'].isna()) | (v_df['Ende'] >= y_start))
        ]
        active_customers = active['Kundennummer'].nunique()
        
        # Schwellenwert-Check
        if active_customers < MIN_ACTIVE_CUSTOMERS:
            continue
        
        # Churn-Metriken
        churned_customers = v_df[
            (v_df['Ende'] >= y_start)
        ]['Kundennummer'].nunique()
        
        new_customers = v_df[
            v_df['Beginn'] >= y_start
        ]['Kundennummer'].nunique()
        
        churn_rate = (churned_customers / active_customers * 100) if active_customers > 0 else 0
        
        # Erweiterte KPIs
        avg_lifetime = calculate_customer_lifetime(v_df, verkäufer)
        reactivation_rate = calculate_reactivation_rate(df, verkäufer, reactivations)
        upselling_rate = calculate_upselling_rate(v_df, verkäufer)
        clv_metrics = calculate_customer_value(v_df, verkäufer)
        
        performance_data.append({
            'Verkäufer': verkäufer,
            'Aktive Kunden': active_customers,
            'Neukunden': new_customers,
            'Verlorene Kunden': churned_customers,
            'Churn Rate (%)': round(churn_rate, 1),
            'Ø Kundenbindung (Monate)': avg_lifetime,
            'Reaktivierungsquote (%)': reactivation_rate,
            'Upselling-Rate (%)': upselling_rate,
            'Ø Produkte/Kunde': clv_metrics['avg_products_per_customer'],
            'Premium-Quote (%)': clv_metrics['premium_product_rate'],
            'Netto-Wachstum': new_customers - churned_customers
        })
    
    detailed_df = pd.DataFrame(performance_data)
    
    if len(detailed_df) == 0:
        return pd.DataFrame(), pd.DataFrame(), {
            'message': f'Keine Verkäufer mit mindestens {MIN_ACTIVE_CUSTOMERS} aktiven Kunden gefunden'
        }
    
    # Performance-Score berechnen (gewichtete Bewertung)
    detailed_df['Performance-Score'] = (
        (100 - detailed_df['Churn Rate (%)']) * 0.3 +  # Niedrige Churn = gut
        detailed_df['Ø Kundenbindung (Monate)'] * 0.2 +  # Lange Bindung = gut
        detailed_df['Reaktivierungsquote (%)'] * 0.2 +  # Hohe Reaktivierung = gut
        detailed_df['Upselling-Rate (%)'] * 0.2 +  # Viele Produkte = gut
        (detailed_df['Netto-Wachstum'] / detailed_df['Aktive Kunden'] * 100) * 0.1  # Wachstum = gut
    ).round(1)
    
    # Ranking
    detailed_df['Rang'] = detailed_df['Performance-Score'].rank(ascending=False, method='min').astype(int)
    detailed_df = detailed_df.sort_values('Rang')
    
    # Summary für Übersicht
    summary = detailed_df[[
        'Rang', 'Verkäufer', 'Aktive Kunden', 'Churn Rate (%)', 
        'Ø Kundenbindung (Monate)', 'Performance-Score'
    ]].copy()
    
    # Insights generieren
    insights = generate_insights(detailed_df)
    
    return detailed_df, summary, insights

def generate_insights(df: pd.DataFrame) -> dict:
    """
    Generiert Insights und Empfehlungen basierend auf den Daten
    """
    insights = {
        'top_performers': [],
        'need_attention': [],
        'strengths': [],
        'opportunities': []
    }
    
    # Top Performer (Top 20%)
    top_threshold = df['Performance-Score'].quantile(0.8)
    top_performers = df[df['Performance-Score'] >= top_threshold]
    
    for _, performer in top_performers.iterrows():
        insights['top_performers'].append({
            'name': performer['Verkäufer'],
            'score': performer['Performance-Score'],
            'best_metric': identify_best_metric(performer)
        })
    
    # Need Attention (Bottom 20%)
    bottom_threshold = df['Performance-Score'].quantile(0.2)
    need_attention = df[df['Performance-Score'] <= bottom_threshold]
    
    for _, performer in need_attention.iterrows():
        insights['need_attention'].append({
            'name': performer['Verkäufer'],
            'score': performer['Performance-Score'],
            'weak_metric': identify_weak_metric(performer)
        })
    
    # Team-Stärken
    if df['Ø Kundenbindung (Monate)'].mean() > 24:
        insights['strengths'].append("Starke Kundenbindung im Team (Ø > 2 Jahre)")
    if df['Upselling-Rate (%)'].mean() > 30:
        insights['strengths'].append("Gutes Cross-Selling im Team")
    if df['Reaktivierungsquote (%)'].mean() > 20:
        insights['strengths'].append("Erfolgreiche Kundenrückgewinnung")
    
    # Verbesserungspotentiale
    if df['Churn Rate (%)'].mean() > 20:
        insights['opportunities'].append("Hohe durchschnittliche Churn-Rate - Kundenbindung stärken")
    if df['Upselling-Rate (%)'].mean() < 20:
        insights['opportunities'].append("Niedrige Upselling-Rate - Cross-Selling Training empfohlen")
    
    return insights

def identify_best_metric(performer: pd.Series) -> str:
    """Identifiziert die stärkste Metrik eines Verkäufers"""
    metrics = {
        'Niedrige Churn': 100 - performer['Churn Rate (%)'],
        'Lange Bindung': performer['Ø Kundenbindung (Monate)'],
        'Hohe Reaktivierung': performer['Reaktivierungsquote (%)'],
        'Starkes Upselling': performer['Upselling-Rate (%)']
    }
    return max(metrics, key=metrics.get)

def identify_weak_metric(performer: pd.Series) -> str:
    """Identifiziert die schwächste Metrik eines Verkäufers"""
    metrics = {
        'Hohe Churn': performer['Churn Rate (%)'],
        'Kurze Bindung': 60 - performer['Ø Kundenbindung (Monate)'],  # Invertiert
        'Wenig Reaktivierung': 50 - performer['Reaktivierungsquote (%)'],  # Invertiert
        'Schwaches Upselling': 50 - performer['Upselling-Rate (%)']  # Invertiert
    }
    return max(metrics, key=metrics.get)
