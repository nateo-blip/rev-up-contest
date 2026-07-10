#!/usr/bin/env python3
"""
REV UP Q3 Fast Start - Selfie Wednesday Tally Script

Reads #us-field-players-only Slack channel for selfie posts on Wednesdays,
maps reps to regions via Snowflake, and generates a tally report.

Usage:
    python3 selfie_tally.py [--date YYYY-MM-DD] [--update-doc] [--post-slack]

If no date is specified, uses the most recent Wednesday.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

CHANNEL = "us-field-players-only"
GOOGLE_DOC_ID = "1CqDjD3cykifzwhnKmwgpNt-lgxbI1fCCN_Ks9sK1SfY"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

# Region overrides for reps whose Snowflake data doesn't match actual org structure
# East = Dan Vazquez's org (incl. Steve McMahon's sub-team)
# Central = Derek Kopkin's org (incl. Phil Skillern, Ramon Quevedo, Alessandra Verne)
# West = Gloria Peña's org (incl. Nate Obermark, Colter Wilson)
REGION_OVERRIDES = {
    # Steve McMahon's team → EAST (Snowflake says Central)
    "Brady Katz": "East",
    "Matt Milos": "East",
    "Alan Prieto": "East",
    "Chris Mendez": "East",
    "Matt Taki": "East",
    "Rebecca Morgan": "East",
    "Steven Bidochka": "East",
    # Chris Moran's team → EAST (Snowflake says Central)
    "Chris Moran": "East",
    "Amanda Wright": "East",
    "Chris Neal": "East",
    "Daniel Bodnar": "East",
    "Daryl Whitley": "East",
    "Kellyn Eagan": "East",
    "Quincy Stang": "East",
    "Sam Agnew-Wieland": "East",
    # Sean Avery's team → EAST (Snowflake says Central)
    "Sean Avery": "East",
    "Boban Perovic": "East",
    "Brittni Fitzgerald": "East",
    "Eddie Brooke": "East",
    "Fabian Pineda": "East",
    "Katy Russo": "East",
    "Sylvia Salimi": "East",
    # Phillip Skillern's direct reports → CENTRAL (Snowflake says East)
    "William McQuaig": "Central",
    "Alexander Rodriguez": "Central",
    "Anjelica Rembert": "Central",
    "Chet Simmons": "Central",
    "Chris Claiborne": "Central",
    "DONOVAN Cuffie": "Central",
    "Kristen Goff": "Central",
    "Lenaye Doussan": "Central",
    "Ron Akins": "Central",
    "Sammy Weitz": "Central",
    "Tracy Cash": "Central",
    # Ramon Quevedo's team → CENTRAL (Snowflake says East)
    "Erick Clausen": "Central",
    "Gustavo Quiroz": "Central",
    "Dwight Richert": "Central",
    "Faith Philpot": "Central",
    "Jose Nunez": "Central",
    "Julia Mulberry": "Central",
    "Manuel Galindo Salazar": "Central",
    "Marlon Salamanca": "Central",
    "Robert Maher": "Central",
    # Alessandra Verne's team → CENTRAL (Snowflake says East)
    "River Sava": "Central",
    "Hernan Madrid": "Central",
    "Tom Brady": "Central",
    "Carolyn Tannura": "Central",
    "Connor White": "Central",
    "Erik Murphy": "Central",
    "Kristian Girolamo": "Central",
    "Matthew Martinez": "Central",
    "Daniel Mance": "Central",
    # Dan Vazquez → EAST (Snowflake says West)
    "Dan Vazquez": "East",
    # Devon Brent (under Scott Hockaday) → CENTRAL (no region in Snowflake)
    "Devon Brent": "Central",
    # Derek Kopkin → CENTRAL (no region in Snowflake)
    "Derek Kopkin": "Central",
}


def run_cmd(cmd, check=True):
    """Run a shell command and return stdout."""
    # Use a script approach to avoid nested quoting issues
    import tempfile as _tf
    script = f'#!/bin/bash\neval "$(/opt/homebrew/bin/brew shellenv)"\n{cmd}\n'
    with _tf.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(script)
        script_path = f.name
    import os as _os
    _os.chmod(script_path, 0o755)
    result = subprocess.run(
        ['bash', script_path], capture_output=True, text=True
    )
    _os.unlink(script_path)
    if check and result.returncode != 0:
        print(f"ERROR: {cmd[:80]}...", file=sys.stderr)
        print(f"  stderr: {result.stderr[:200]}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def get_most_recent_wednesday():
    """Find the most recent Wednesday (including today if Wednesday)."""
    today = datetime.now()
    days_since_wed = (today.weekday() - 2) % 7
    return (today - timedelta(days=days_since_wed)).strftime("%Y-%m-%d")


def fetch_slack_messages(target_date, next_date):
    """Fetch all messages from the channel for the target date."""
    all_messages = []
    cursor = None

    for batch_num in range(5):  # max 5 batches (250 messages)
        cmd = (
            f'sq agent-tools slack read-channels '
            f'--channels "{CHANNEL}" '
            f'--limit 50 '
            f'--after-date "{target_date}" '
            f'--before-date "{next_date}" '
            f'--timezone "America/New_York"'
        )
        if cursor:
            cmd += f' --cursor "{cursor}"'

        output = run_cmd(cmd)
        data = json.loads(output)
        result = data["results"][0]
        all_messages.extend(result["messages"])

        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor", "")
        if not cursor:
            break

    return all_messages


def fetch_region_map():
    """Get LDAP -> region mapping from Snowflake."""
    import tempfile, os
    query = (
        "SELECT LDAP, FULL_NAME, REGION, DIRECT_LEAD "
        "FROM APP_SALES.APP_SALES_ETL.FACT_FIELD_SALES_EMPLOYMENT_CURRENT "
        "WHERE ACTIVE_STATUS = 'Active' "
        "AND (IS_SALES_REP = TRUE OR IS_SALES_MANAGEMENT = TRUE) "
        "ORDER BY REGION, FULL_NAME"
    )
    # Write query to temp file to avoid shell escaping issues with single quotes
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
        f.write(query)
        query_file = f.name

    cmd = (
        f'sq agent-tools query-expert execute-query '
        f'--query "$(cat {query_file})" '
        f'--database "APP_SALES"'
    )
    output = run_cmd(cmd)
    os.unlink(query_file)
    data = json.loads(output)

    if not data.get("data"):
        print(f"ERROR: No data returned from Snowflake. Status: {data.get('status')}", file=sys.stderr)
        print(f"  Full response keys: {list(data.keys())}", file=sys.stderr)
        sys.exit(1)

    region_map = {}
    for row in data["data"]:
        # Some rows have NULL region (omitted from JSON) - skip those
        region = row.get("REGION")
        if not region:
            continue
        region_map[row["LDAP"]] = {
            "name": row["FULL_NAME"],
            "region": region,
            "lead": row.get("DIRECT_LEAD", "Unknown"),
        }
    print(f"   {len(region_map)} reps with region assignments loaded")

    # Apply region overrides for known mismatches
    for ldap, info in region_map.items():
        if info["name"] in REGION_OVERRIDES:
            old_region = info["region"]
            info["region"] = REGION_OVERRIDES[info["name"]]
            print(f"   Override: {info['name']} {old_region} → {info['region']}")

    return region_map


def count_selfies(messages, target_date, region_map):
    """Count selfie posts by region."""
    selfie_posts = defaultdict(list)

    for msg in messages:
        time_str = msg.get("time", "")
        if target_date not in time_str:
            continue

        files = msg.get("files", [])
        if not files:
            continue

        images = [f for f in files if f.get("mimetype", "").startswith("image/")]
        if not images:
            continue

        username = msg.get("user", {}).get("username", "")
        real_name = msg.get("user", {}).get("real_name", "")
        selfie_posts[username].append({
            "time": time_str,
            "images": len(images),
            "real_name": real_name,
            "text": msg.get("text", "")[:100],
        })

    # Tally by region
    region_tally = defaultdict(lambda: {"reps": [], "total_posts": 0, "total_images": 0})
    unmatched = []

    for username, posts in selfie_posts.items():
        total_images = sum(p["images"] for p in posts)
        if username in region_map:
            info = region_map[username]
            region = info["region"]
            region_tally[region]["reps"].append({
                "name": info["name"],
                "ldap": username,
                "lead": info["lead"],
                "posts": len(posts),
                "images": total_images,
            })
            # Count only 1 selfie per rep, regardless of multiple posts
            region_tally[region]["total_posts"] += 1
            region_tally[region]["total_images"] += 1
        else:
            unmatched.append({
                "username": username,
                "real_name": posts[0]["real_name"] if posts else "",
                "posts": len(posts),
                "images": total_images,
            })

    return region_tally, unmatched


def generate_report(target_date, region_tally, unmatched, alis_pick=None):
    """Generate the tally report (text + JSON)."""
    sorted_regions = sorted(region_tally.items(), key=lambda x: -x[1]["total_images"])
    total_selfies = sum(r["total_images"] for _, r in sorted_regions)
    total_reps = sum(len(r["reps"]) for _, r in sorted_regions)
    winner_region = sorted_regions[0][0] if sorted_regions else "TBD"

    # Text report
    lines = []
    lines.append(f"Selfie Day ({target_date})")
    lines.append("Final tally")
    lines.append("")
    lines.append("Region\tPoints")

    medals = ["🥇", "🥈", "🥉"]
    for i, (region, data) in enumerate(sorted_regions):
        lines.append(f"{region}\t{data['total_images']}")

    lines.append("")
    lines.append(f"Total selfies counted: {total_selfies} 🎉")
    lines.append("Current leaderboard:")
    for i, (region, data) in enumerate(sorted_regions):
        medal = medals[i] if i < 3 else "  "
        lines.append(f"{medal} {region}: {data['total_images']}")

    lines.append("")
    lines.append(f"🏆 Region Winner: {winner_region} (+10 pts)")

    if alis_pick:
        lines.append(f"⭐ Ali's Pick: {alis_pick} (+10 pts)")
    else:
        lines.append("⭐ Ali's Pick: [TBD]")

    lines.append("")
    lines.append("--- Individual Submissions ---")
    for region, data in sorted_regions:
        lines.append(f"\n{region} ({len(data['reps'])} reps, {data['total_images']} selfies):")
        for rep in sorted(data["reps"], key=lambda x: -x["images"]):
            multi = f" ({rep['images']} photos)" if rep["images"] > 1 else ""
            lines.append(f"  • {rep['name']} - {rep['lead']}{multi}")

    if unmatched:
        lines.append("\n⚠️ Unmatched (not in active roster):")
        for u in unmatched:
            lines.append(f"  • @{u['username']} ({u['real_name']}) - {u['images']} images")

    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    text_report = "\n".join(lines)

    # JSON report
    json_report = {
        "date": target_date,
        "total_selfies": total_selfies,
        "total_reps": total_reps,
        "winner_region": winner_region,
        "alis_pick": alis_pick,
        "regions": {},
        "unmatched": unmatched,
        "generated_at": datetime.now().isoformat(),
    }
    for region, data in sorted_regions:
        json_report["regions"][region] = {
            "selfie_count": data["total_images"],
            "rep_count": len(data["reps"]),
            "reps": data["reps"],
        }

    return text_report, json_report


def update_google_doc(text_report, target_date):
    """Append the tally to the Google Doc."""
    # Read current content
    cmd = (
        f'eval "$(/opt/homebrew/bin/brew shellenv)" && '
        f'sq agent-tools google-drive read '
        f'--id-or-url "https://docs.google.com/document/d/{GOOGLE_DOC_ID}/edit"'
    )
    output = run_cmd(cmd)
    current = json.loads(output)
    current_content = current.get("result", "")

    # Upsert with new content appended
    # Use docs-write to append
    escaped_report = text_report.replace("'", "'\\''")
    cmd = (
        f'eval "$(/opt/homebrew/bin/brew shellenv)" && '
        f'sq agent-tools google-drive upsert '
        f'--id-or-url "https://docs.google.com/document/d/{GOOGLE_DOC_ID}/edit" '
        f'--content \'{escaped_report}\''
    )
    result = run_cmd(cmd, check=False)
    if "error" in result.lower():
        print(f"⚠️  Could not update Google Doc automatically: {result[:100]}", file=sys.stderr)
        print("   Report saved locally - copy/paste manually if needed.", file=sys.stderr)
        return False
    return True


def post_to_slack(text_report):
    """Post the tally summary to the channel."""
    # Create a condensed version for Slack
    lines = text_report.split("\n")
    # Take just the summary portion
    summary_lines = []
    for line in lines:
        if "--- Individual Submissions ---" in line:
            break
        summary_lines.append(line)

    summary = "\n".join(summary_lines)
    escaped = summary.replace("'", "'\\''").replace('"', '\\"')

    cmd = (
        f'eval "$(/opt/homebrew/bin/brew shellenv)" && '
        f'sq agent-tools slack post-message '
        f'--channels "{CHANNEL}" '
        f'--text \'{escaped}\''
    )
    result = run_cmd(cmd, check=False)
    return "error" not in result.lower()


def main():
    parser = argparse.ArgumentParser(description="REV UP Selfie Wednesday Tally")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to most recent Wednesday")
    parser.add_argument("--update-doc", action="store_true", help="Update the Google Doc with results")
    parser.add_argument("--post-slack", action="store_true", help="Post results to Slack channel")
    parser.add_argument("--alis-pick", help="Name of Ali's pick winner")
    args = parser.parse_args()

    target_date = args.date or get_most_recent_wednesday()
    next_date = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📸 REV UP Selfie Tally - {target_date}")
    print("=" * 50)

    # Fetch data
    print("📡 Reading Slack channel...")
    messages = fetch_slack_messages(target_date, next_date)
    print(f"   Found {len(messages)} messages")

    print("🗄️  Fetching region mapping from Snowflake...")
    region_map = fetch_region_map()
    print(f"   {len(region_map)} active reps loaded")

    # Count and tally
    print("📊 Counting selfies...")
    region_tally, unmatched = count_selfies(messages, target_date, region_map)

    # Generate report
    text_report, json_report = generate_report(
        target_date, region_tally, unmatched, args.alis_pick
    )

    # Print report
    print("\n" + text_report)

    # Save JSON report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"selfie_tally_{target_date}.json"
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)
    print(f"\n✅ JSON report saved to: {json_path}")

    # Optional: Update Google Doc
    if args.update_doc:
        print("\n📝 Updating Google Doc...")
        if update_google_doc(text_report, target_date):
            print("   ✅ Google Doc updated")
        else:
            print("   ⚠️  Google Doc update failed - see report above")

    # Optional: Post to Slack
    if args.post_slack:
        print("\n💬 Posting to Slack...")
        if post_to_slack(text_report):
            print("   ✅ Posted to #us-field-players-only")
        else:
            print("   ⚠️  Slack post failed")

    return json_report


if __name__ == "__main__":
    main()
