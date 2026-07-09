#!/bin/bash
# REV UP Q3 Fast Start - Selfie Wednesday Tally Script
# Reads #us-field-players-only Slack channel for selfie posts on Wednesdays
# Maps reps to regions and generates a tally report
#
# Usage: ./selfie_tally.sh [date]
#   date: YYYY-MM-DD (defaults to most recent Wednesday)
#
# Output: JSON report with regional counts and individual submissions

set -euo pipefail
eval "$(/opt/homebrew/bin/brew shellenv)"

# Determine target date (most recent Wednesday if not specified)
if [ -n "${1:-}" ]; then
    TARGET_DATE="$1"
else
    # Find most recent Wednesday
    DOW=$(date +%u)  # 1=Mon, 3=Wed, 7=Sun
    if [ "$DOW" -ge 3 ]; then
        DAYS_BACK=$((DOW - 3))
    else
        DAYS_BACK=$((DOW + 4))
    fi
    TARGET_DATE=$(date -v-${DAYS_BACK}d +%Y-%m-%d)
fi

NEXT_DATE=$(date -j -f "%Y-%m-%d" "$TARGET_DATE" -v+1d +%Y-%m-%d)
CHANNEL="us-field-players-only"

echo "📸 REV UP Selfie Tally - $TARGET_DATE"
echo "=================================="
echo ""

# Step 1: Read all selfie posts from the target date
echo "Reading #$CHANNEL for $TARGET_DATE..."

# First batch
BATCH1=$(sq agent-tools slack read-channels \
    --channels "$CHANNEL" \
    --limit 50 \
    --after-date "$TARGET_DATE" \
    --before-date "$NEXT_DATE" \
    --timezone "America/New_York" 2>/dev/null)

# Check if there's more
HAS_MORE=$(echo "$BATCH1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['results'][0].get('has_more', False))")
CURSOR=$(echo "$BATCH1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['results'][0].get('next_cursor', ''))" 2>/dev/null || echo "")

ALL_MESSAGES="$BATCH1"

# Get additional batches if needed
if [ "$HAS_MORE" = "True" ] && [ -n "$CURSOR" ]; then
    BATCH2=$(sq agent-tools slack read-channels \
        --channels "$CHANNEL" \
        --limit 50 \
        --after-date "$TARGET_DATE" \
        --before-date "$NEXT_DATE" \
        --timezone "America/New_York" \
        --cursor "$CURSOR" 2>/dev/null)
    ALL_MESSAGES=$(echo "$BATCH1"$'\n---BATCH---\n'"$BATCH2")
fi

# Step 2: Get region mapping from Snowflake
echo "Fetching region mapping from Snowflake..."
REGION_DATA=$(sq agent-tools query-expert execute-query --query "
SELECT LDAP, FULL_NAME, REGION, DIRECT_LEAD
FROM APP_SALES.APP_SALES_ETL.FACT_FIELD_SALES_EMPLOYMENT_CURRENT
WHERE ACTIVE_STATUS = 'Active'
  AND IS_SALES_REP = TRUE
ORDER BY REGION, FULL_NAME
" --database "APP_SALES" 2>/dev/null)

# Step 3: Process everything in Python
python3 << 'PYTHON_SCRIPT'
import json
import sys
from collections import defaultdict
from datetime import datetime

target_date = "$TARGET_DATE"

# Parse Slack messages (handle multiple batches)
all_messages_raw = '''$ALL_MESSAGES'''
batches = all_messages_raw.split('---BATCH---')

all_messages = []
for batch_raw in batches:
    batch_raw = batch_raw.strip()
    if not batch_raw:
        continue
    try:
        batch = json.loads(batch_raw)
        all_messages.extend(batch['results'][0]['messages'])
    except:
        continue

# Parse region data
region_data = json.loads('''$REGION_DATA''')
region_map = {}  # ldap -> {name, region, lead}
for row in region_data['data']:
    region_map[row['LDAP']] = {
        'name': row['FULL_NAME'],
        'region': row['REGION'],
        'lead': row['DIRECT_LEAD']
    }

# Count selfies: messages with image files on target date
selfie_posts = defaultdict(list)  # username -> list of timestamps
for msg in all_messages:
    time_str = msg.get('time', '')
    if target_date not in time_str:
        continue
    files = msg.get('files', [])
    if not files:
        continue
    has_image = any(f.get('mimetype', '').startswith('image/') for f in files)
    if has_image:
        username = msg.get('user', {}).get('username', '')
        real_name = msg.get('user', {}).get('real_name', '')
        img_count = sum(1 for f in files if f.get('mimetype', '').startswith('image/'))
        selfie_posts[username].append({
            'time': time_str,
            'images': img_count,
            'text': msg.get('text', '')[:100]
        })

# Tally by region
region_tally = defaultdict(lambda: {'reps': [], 'total_posts': 0, 'total_images': 0})
unmatched = []

for username, posts in selfie_posts.items():
    total_images = sum(p['images'] for p in posts)
    if username in region_map:
        info = region_map[username]
        region = info['region']
        region_tally[region]['reps'].append({
            'name': info['name'],
            'ldap': username,
            'lead': info['lead'],
            'posts': len(posts),
            'images': total_images
        })
        region_tally[region]['total_posts'] += len(posts)
        region_tally[region]['total_images'] += total_images
    else:
        unmatched.append({'username': username, 'posts': len(posts), 'images': total_images})

# Sort regions by total images (descending)
sorted_regions = sorted(region_tally.items(), key=lambda x: -x[1]['total_images'])

# Print report
print(f"\n📸 SELFIE WEDNESDAY TALLY - {target_date}")
print("=" * 50)
total_selfies = sum(r['total_images'] for _, r in sorted_regions)
total_reps = sum(len(r['reps']) for _, r in sorted_regions)
print(f"\nTotal selfies: {total_selfies} 🎉")
print(f"Total participating reps: {total_reps}")
print(f"\n{'='*50}")
print("REGIONAL STANDINGS:")
print(f"{'='*50}")

medals = ['🥇', '🥈', '🥉']
for i, (region, data) in enumerate(sorted_regions):
    medal = medals[i] if i < 3 else '  '
    print(f"\n{medal} {region}: {data['total_images']} selfies ({len(data['reps'])} reps)")
    print(f"   +10 POINTS" if i == 0 else "")
    for rep in sorted(data['reps'], key=lambda x: -x['images']):
        multi = f" ({rep['images']} photos)" if rep['images'] > 1 else ""
        print(f"     • {rep['name']} ({rep['lead']}){multi}")

if unmatched:
    print(f"\n⚠️  Unmatched users (not in active field sales roster):")
    for u in unmatched:
        print(f"     • @{u['username']} ({u['images']} images)")

# Winner announcement
winner_region = sorted_regions[0][0] if sorted_regions else "TBD"
print(f"\n{'='*50}")
print(f"🏆 SELFIE WEDNESDAY WINNER: {winner_region} (+10 pts)")
print(f"{'='*50}")
print(f"\n📌 Lizzy's Pick (org-wide +10 pts): [TO BE ANNOUNCED]")
print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Also output JSON for programmatic use
report = {
    'date': target_date,
    'total_selfies': total_selfies,
    'total_reps': total_reps,
    'winner_region': winner_region,
    'regions': {region: {
        'selfie_count': data['total_images'],
        'rep_count': len(data['reps']),
        'reps': data['reps']
    } for region, data in sorted_regions},
    'lizzys_pick': None,
    'generated_at': datetime.now().isoformat()
}

with open(f'/Users/nateobermark/rev-up-contest/reports/selfie_tally_{target_date}.json', 'w') as f:
    json.dump(report, f, indent=2)
print(f"\n✅ JSON report saved to: rev-up-contest/reports/selfie_tally_{target_date}.json")

PYTHON_SCRIPT
