import json
from datetime import datetime
import math

def parse_date(date_str):
    if not date_str:
        return None
    try:
        # Pipedrive usually returns "YYYY-MM-DD HH:MM:SS"
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def calculate_percentile(sorted_data, percentile):
    if not sorted_data:
        return 0
    k = (len(sorted_data) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)]
    d1 = sorted_data[int(c)]
    return d0 + (d1 - d0) * (k - f)

def analyze():
    print("Loading data...")
    with open('deals.json', 'r', encoding='utf-8') as f:
        deals = json.load(f)

    won_durations = []
    
    print(f"Analyzing {len(deals)} deals...")

    for deal in deals:
        if deal.get('status') == 'won':
            add_time = parse_date(deal.get('add_time'))
            won_time = parse_date(deal.get('won_time'))

            if add_time and won_time:
                # Calculate duration in days
                duration_days = (won_time - add_time).total_seconds() / (24 * 3600)
                # Filter out negative durations (data errors) or zero (instant wins)
                if duration_days >= 0:
                    won_durations.append(duration_days)

    if not won_durations:
        print("No won deals found with valid dates.")
        return

    won_durations.sort()
    count = len(won_durations)
    
    # Calculate metrics
    p50 = calculate_percentile(won_durations, 0.50) # Median
    p75 = calculate_percentile(won_durations, 0.75)
    p90 = calculate_percentile(won_durations, 0.90)
    p95 = calculate_percentile(won_durations, 0.95)
    p99 = calculate_percentile(won_durations, 0.99)
    avg = sum(won_durations) / count
    max_duration = won_durations[-1]
    min_duration = won_durations[0]

    # Calculate Date Range for Context
    won_dates = [parse_date(d.get('won_time')) for d in deals if d.get('status') == 'won' and d.get('won_time')]
    won_dates.sort()
    earliest_date = won_dates[0].strftime("%b %Y")
    latest_date = won_dates[-1].strftime("%b %Y")

    print("\n" + "="*40)
    print("SALES CYCLE ANALYSIS (Time to Won)")
    print("="*40)
    print(f"Date Range:      {earliest_date} - {latest_date}")
    print(f"Total Won Deals Analyzed: {count}")
    print("-" * 40)
    print(f"Average Cycle:   {avg:.2f} days")
    print(f"Fastest Win:     {min_duration:.2f} days")
    print(f"Slowest Win:     {max_duration:.2f} days")
    print("-" * 40)
    print("PERCENTILES (Forecast Metrics)")
    print(f"50% of deals close within: {p50:.2f} days (Median)")
    print(f"75% of deals close within: {p75:.2f} days")
    print(f"90% of deals close within: {p90:.2f} days")
    print(f"95% of deals close within: {p95:.2f} days")
    print(f"99% of deals close within: {p99:.2f} days <--- YOUR METRIC")
    print("="*40)

if __name__ == "__main__":
    analyze()
