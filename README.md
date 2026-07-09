# REV UP - Q3 Fast Start Contest

**Field Sales · All Regions · July 1 – August 1, 2026**

Created by: Nate Obermark, Phillip Skillern, Steve McMahon

## Overview

REV UP is a Q3 Fast Start contest for all Field Sales reps across East, West, and Central regions. The contest tracks Signs, Activations, Square Loans, and bonus activities to determine both individual and regional winners.

## Scoring Rules

### Signs (New Signed Accounts)
| Vertical | Points |
|----------|--------|
| Services / Retail | 3 pts |
| F&B | 1 pt |

### Activations (Live and Processing)
| Vertical | Points |
|----------|--------|
| Services / Retail | 3 pts |
| F&B | 1 pt |

### Double Points Bonus
- **Signed + Activated in July** (250k minimum opportunity amount)
- **Double points on ALL verticals** (both sign and activation points are doubled)

### Square Loans
| Loan Amount | Points |
|-------------|--------|
| Above $75k | 9 pts |
| Up to $75k | 6 pts |
| Up to $25k | 3 pts |

### Bonus Points
| Bonus | Points | Frequency |
|-------|--------|-----------|
| Selfie Day | +10 pts | Wednesdays (Lizzy picks 1 winner org-wide) |
| Slack Engagement | +10 pts | Most engaged region wins |

## Prize
🏆 **Trophy + Pride** — Winning Region (East vs. West vs. Central)

## Data Sources

| Category | Source Table | Join Logic |
|----------|-------------|------------|
| Signs | `APP_SALES.APP_SALES_ETL.SMB_CONTRACT_OPPORTUNITIES` | CONTRACT_SIGNED_DATE in contest window |
| Activations | `APP_SALES.APP_SALES_ETL.ACTIVATION_CREDIT_VIEW` | ACTIVATION_DATE in contest window |
| Loans | `APP_CAPITAL.APP_CAPITAL.PLAN_GROUPS` | ACTIVATED_AT in contest window, joined via VDIM_USER |
| Rep Roster | `APP_SALES.APP_SALES_ETL.FACT_FIELD_SALES_EMPLOYMENT_CURRENT` | IS_SALES_REP = TRUE, SALES_TEAM = 'Sales - US Field' |
| Merchant Vertical | `APP_BI.HEXAGON.VDIM_USER` | BUSINESS_CATEGORY → F&B vs Services/Retail |
| Bonus Points | `APP_SALES.APP_SALES_ETL.REVUP_BONUS_POINTS` | Manual entry table |

## SQL Views

| File | Description |
|------|-------------|
| `01_signs_scoring.sql` | Signs scoring with vertical classification |
| `02_activations_scoring.sql` | Activations scoring with vertical classification |
| `03_double_points.sql` | Double points bonus for sign+activate in July (250k min) |
| `04_loans_scoring.sql` | Square Loans scoring by tier |
| `05_combined_leaderboard.sql` | Combined leaderboard aggregating all categories |
| `06_regional_standings.sql` | Regional totals (East vs West vs Central) |
| `07_bonus_tracking.sql` | Manual bonus points table + full leaderboard view |

## App

The REV UP Explorer app provides:
- 🏆 Regional leaderboard (East vs. West vs. Central)
- 👤 Individual rep standings with point breakdown
- ⏱️ Countdown timer to August 1
- 📊 Scoring breakdown by category
- 🎯 Selfie Day & Slack Engagement bonus tracking

## Setup

1. Run the SQL files in order (01-07) against Snowflake
2. The app pulls from the views created above
3. Bonus points are entered manually into `REVUP_BONUS_POINTS` table
