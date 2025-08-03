"""
Churn Analytics Module
Enthält alle Berechnungsfunktionen für die Churn-Analyse
"""

import pandas as pd
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta

RELEVANT_GROUPS = [
    "Firmendaten Manager", "Website", "SEO", "Google Ads",
    "Postings", "Superkombis", "Social Media Werbeanzeigen"
]

# Reseller-Kundennummern (werden bei True Churn ignoriert)
RESELLER_CUSTOMERS = [1902101, 1909143, 1903121, 1905146, 1911102]

RESELLER_NAMES = {
    1902101: "Onco",
    1909143: "Russmedia Verlag",
    1903121: "Russmedia Digital", 
    1905146: "Northlight",
    1911102: "Sam Solution"
}

def last_12_full_months(ref_date: pd.Timestamp):
    """Gibt die letzten 12 vollen Monate zurück"""
    last_full = ref_date.replace(day=1) - pd.Timedelta(days=1)
    months = []
    for i in range(12):
        start = (last_full - relativedelta(months=i)).replace(day=1)
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        months.append((start, end))
    return list(reversed(months))

def map_group(row):
    """Mappt Produktkategorien zu analysierbaren Gruppen"""
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
    Analysiert Kundenverlauf und identifiziert echte Kündigungen vs. Reaktivierungen
    Reseller werden hier ausgeschlossen, da sie anders berechnet werden
    """
    df_no_reseller = df[~df['Kundennummer'].isin(RESELLER_CUSTOMERS)].copy()
    df_sorted = df_no_reseller.sort_values(['Kundennummer', 'ProductGroup', 'Beginn'])
    
    churn_events = []
    reactivations = []
    
    for (kunde, group), customer_df in df_sorted.groupby(['Kundennummer', 'ProductGroup']):
        customer_df = customer_df.reset_index(drop=True)
        
        for i, row in customer_df.iterrows():
            if pd.isna(row['Ende']):
                continue
                
            end_date = row['Ende']
            future_contracts = customer_df[
                (customer_df['Beginn'] > end_date) & 
                (customer_df.index > i)
            ]
            
            if len(future_contracts) > 0:
                next_start = future_contracts['Beginn'].min()
                gap_days = (next_start - end_date).days
                
                if gap_days <= grace_period_days:
                    reactivations.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'Ende': end_date,
                        'NeuerBeginn': next_start,
                        'Luecke_Tage': gap_days,
                        'Typ': 'Reaktivierung'
                    })
                else:
                    churn_events.append({
                        'Kundennummer': kunde,
                        'ProductGroup': group,
                        'ChurnDatum': end_date,
                        'Typ': 'Echte Kündigung (lange Pause)'
                    })
            else:
                churn_events.append({
                    'Kundennummer': kunde,
                    'ProductGroup': group,
                    'ChurnDatum': end_date,
                    'Typ': 'Echte Kündigung (kein Folgevertrag)'
                })
    
    return pd.DataFrame(churn_events), pd.DataFrame(reactivations)

def calculate_yearly_churn(df: pd.DataFrame, churn_events: pd.DataFrame, start_year: int = 2020):
    """Berechnet Jahres-Churn Raten"""
    today = pd.Timestamp.today()
    end_year = today.year
    yearly_records = []
    
    for year in range(start_year, end_year + 1):
        y_start = pd.Timestamp(f"{year}-01-01")
        y_end = today if year == end_year else pd.Timestamp(f"{year}-12-31")
        
        for group in RELEVANT_GROUPS:
            group_df = df[df['ProductGroup'] == group]
            
            if len(group_df) == 0:
                continue
            
            reseller_df = group_df[group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
            regular_df = group_df[~group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
            
            active_customers = set()
            for kunde, kunde_df in regular_df.groupby('Kundennummer'):
                kunde_active = kunde_df[
                    (kunde_df['Beginn'] < y_start) & 
                    ((kunde_df['Ende'].isna()) | (kunde_df['Ende'] >= y_start))
                ]
                if len(kunde_active) > 0:
                    active_customers.add(kunde)
            
            reseller_active = reseller_df[
                (reseller_df['Beginn'] < y_start) & 
                ((reseller_df['Ende'].isna()) | (reseller_df['Ende'] >= y_start))
            ]
            num_reseller_active = len(reseller_active)
            
            regular_churned = set(churn_events[
                (churn_events['ProductGroup'] == group) &
                (churn_events['ChurnDatum'] >= y_start) & 
                (churn_events['ChurnDatum'] <= y_end)
            ]['Kundennummer'].unique())
            
            reseller_churned = reseller_df[
                (reseller_df['Ende'] >= y_start) & 
                (reseller_df['Ende'] <= y_end)
            ]
            num_reseller_churned = len(reseller_churned)
            
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

def calculate_waterfall_data(df: pd.DataFrame, churn_events: pd.DataFrame, year: int):
    """Berechnet Daten für Waterfall-Chart"""
    y_start = pd.Timestamp(f"{year}-01-01")
    y_end = pd.Timestamp(f"{year}-12-31") if year < pd.Timestamp.today().year else pd.Timestamp.today()
    
    waterfall_data = []
    
    for group in RELEVANT_GROUPS:
        group_df = df[df['ProductGroup'] == group]
        
        if len(group_df) == 0:
            continue
            
        start_customers = group_df[
            (group_df['Beginn'] < y_start) & 
            ((group_df['Ende'].isna()) | (group_df['Ende'] >= y_start))
        ]['Kundennummer'].nunique()
        
        new_customers = group_df[
            (group_df['Beginn'] >= y_start) & 
            (group_df['Beginn'] <= y_end)
        ]['Kundennummer'].nunique()
        
        churned_customers = len(set(churn_events[
            (churn_events['ProductGroup'] == group) &
            (churn_events['ChurnDatum'] >= y_start) & 
            (churn_events['ChurnDatum'] <= y_end)
        ]['Kundennummer'].unique()))
        
        reseller_df = group_df[group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
        reseller_churned = len(reseller_df[
            (reseller_df['Ende'] >= y_start) & 
            (reseller_df['Ende'] <= y_end)
        ])
        
        total_churned = churned_customers + reseller_churned
        end_customers = start_customers + new_customers - total_churned
        
        waterfall_data.append({
            'Gruppe': group,
            'Start': start_customers,
            'Neukunden': new_customers,
            'Verluste': -total_churned,
            'Ende': end_customers
        })
    
    return pd.DataFrame(waterfall_data)

def analyze_sales_performance(df: pd.DataFrame, churn_events: pd.DataFrame):
    """Analysiert Churn-Performance nach Verkäufern"""
    if 'Zugewiesen an' not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    
    df['Verkäufer'] = df['Zugewiesen an'].fillna('Nicht zugewiesen').str.strip()
    
    current_year = pd.Timestamp.today().year
    y_start = pd.Timestamp(f"{current_year}-01-01")
    
    performance_data = []
    
    for verkäufer in df['Verkäufer'].unique():
        v_df = df[df['Verkäufer'] == verkäufer]
        
        for group in RELEVANT_GROUPS:
            vg_df = v_df[v_df['ProductGroup'] == group]
            
            if len(vg_df) == 0:
                continue
            
            active = vg_df[
                (vg_df['Beginn'] < y_start) & 
                ((vg_df['Ende'].isna()) | (vg_df['Ende'] >= y_start))
            ]
            active_customers = active['Kundennummer'].nunique()
            
            churned_customers = vg_df[
                (vg_df['Ende'] >= y_start)
            ]['Kundennummer'].nunique()
            
            new_customers = vg_df[
                vg_df['Beginn'] >= y_start
            ]['Kundennummer'].nunique()
            
            churn_rate = (churned_customers / active_customers * 100) if active_customers > 0 else 0
            
            performance_data.append({
                'Verkäufer': verkäufer,
                'Produktgruppe': group,
                'Aktive Kunden': active_customers,
                'Neukunden': new_customers,
                'Verlorene Kunden': churned_customers,
                'Churn Rate (%)': round(churn_rate, 1)
            })
    
    performance_df = pd.DataFrame(performance_data)
    
    if len(performance_df) > 0:
        summary = performance_df.groupby('Verkäufer').agg({
            'Aktive Kunden': 'sum',
            'Neukunden': 'sum',
            'Verlorene Kunden': 'sum'
        }).reset_index()
        summary['Churn Rate (%)'] = round(
            (summary['Verlorene Kunden'] / summary['Aktive Kunden'] * 100).fillna(0), 1
        )
        summary['Netto-Wachstum'] = summary['Neukunden'] - summary['Verlorene Kunden']
        summary = summary.sort_values('Churn Rate (%)', ascending=True)
    else:
        summary = pd.DataFrame()
    
    return performance_df, summary

def calculate_current_year_churn(df: pd.DataFrame, churn_events: pd.DataFrame):
    """Berechnet aktuellen Jahres-Churn"""
    today = pd.Timestamp.today()
    y_start = pd.Timestamp(f"{today.year}-01-01")
    
    current_churn = []
    
    for group in RELEVANT_GROUPS:
        group_df = df[df['ProductGroup'] == group]
        
        if len(group_df) == 0:
            current_churn.append({
                'Produktgruppe': group,
                'Aktive Kunden': 0,
                'Verluste': 0,
                'Churn Rate (%)': 0.0
            })
            continue
        
        reseller_df = group_df[group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
        regular_df = group_df[~group_df['Kundennummer'].isin(RESELLER_CUSTOMERS)]
        
        active_customers = set()
        for kunde, kunde_df in regular_df.groupby('Kundennummer'):
            kunde_active = kunde_df[
                (kunde_df['Beginn'] < y_start) & 
                ((kunde_df['Ende'].isna()) | (kunde_df['Ende'] >= y_start))
            ]
            if len(kunde_active) > 0:
                active_customers.add(kunde)
        
        reseller_active = len(reseller_df[
            (reseller_df['Beginn'] < y_start) & 
            ((reseller_df['Ende'].isna()) | (reseller_df['Ende'] >= y_start))
        ])
        
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
            'Verluste': total_churned,
            'Churn Rate (%)': round(churn_rate, 1)
        })
    
    return pd.DataFrame(current_churn)
