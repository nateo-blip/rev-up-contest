-- REV UP Contest: Combined Leaderboard
-- Aggregates all scoring categories into a single leaderboard view
-- Includes: Signs, Activations, Double Points Bonus, Square Loans

CREATE OR REPLACE VIEW APP_SALES.APP_SALES_ETL.VW_REVUP_LEADERBOARD AS
WITH signs_points AS (
    SELECT 
        REP_NAME,
        REP_LDAP,
        MANAGER,
        REGION,
        SUM(BASE_POINTS) AS SIGN_POINTS,
        COUNT(*) AS SIGN_COUNT
    FROM APP_SALES.APP_SALES_ETL.VW_REVUP_SIGNS
    GROUP BY 1, 2, 3, 4
),

activation_points AS (
    SELECT 
        REP_NAME,
        REP_LDAP,
        MANAGER,
        REGION,
        SUM(BASE_POINTS) AS ACTIVATION_POINTS,
        COUNT(*) AS ACTIVATION_COUNT
    FROM APP_SALES.APP_SALES_ETL.VW_REVUP_ACTIVATIONS
    GROUP BY 1, 2, 3, 4
),

double_bonus_points AS (
    SELECT 
        REP_NAME,
        REP_LDAP,
        MANAGER,
        REGION,
        SUM(TOTAL_BONUS_POINTS) AS DOUBLE_BONUS_POINTS,
        COUNT(*) AS DOUBLE_BONUS_COUNT
    FROM APP_SALES.APP_SALES_ETL.VW_REVUP_DOUBLE_POINTS
    GROUP BY 1, 2, 3, 4
),

loan_points AS (
    SELECT 
        REP_NAME,
        REP_LDAP,
        MANAGER,
        REGION,
        SUM(POINTS) AS LOAN_POINTS,
        COUNT(*) AS LOAN_COUNT
    FROM APP_SALES.APP_SALES_ETL.VW_REVUP_LOANS
    GROUP BY 1, 2, 3, 4
),

-- All reps roster (base)
all_reps AS (
    SELECT 
        FULL_NAME AS REP_NAME,
        LDAP AS REP_LDAP,
        DIRECT_LEAD AS MANAGER,
        REGION
    FROM APP_SALES.APP_SALES_ETL.FACT_FIELD_SALES_EMPLOYMENT_CURRENT
    WHERE IS_SALES_REP = TRUE
        AND SALES_TEAM = 'Sales - US Field'
        AND ACTIVE_STATUS = 'Active'
        AND REGION IS NOT NULL
)

SELECT 
    r.REP_NAME,
    r.REP_LDAP,
    r.MANAGER,
    r.REGION,
    COALESCE(s.SIGN_POINTS, 0) AS SIGN_POINTS,
    COALESCE(s.SIGN_COUNT, 0) AS SIGN_COUNT,
    COALESCE(a.ACTIVATION_POINTS, 0) AS ACTIVATION_POINTS,
    COALESCE(a.ACTIVATION_COUNT, 0) AS ACTIVATION_COUNT,
    COALESCE(d.DOUBLE_BONUS_POINTS, 0) AS DOUBLE_BONUS_POINTS,
    COALESCE(d.DOUBLE_BONUS_COUNT, 0) AS DOUBLE_BONUS_COUNT,
    COALESCE(l.LOAN_POINTS, 0) AS LOAN_POINTS,
    COALESCE(l.LOAN_COUNT, 0) AS LOAN_COUNT,
    -- Total points (signs + activations + double bonus + loans)
    -- Note: Selfie Day and Slack Engagement bonuses are tracked separately (manual entry)
    (COALESCE(s.SIGN_POINTS, 0) 
     + COALESCE(a.ACTIVATION_POINTS, 0) 
     + COALESCE(d.DOUBLE_BONUS_POINTS, 0) 
     + COALESCE(l.LOAN_POINTS, 0)) AS TOTAL_POINTS
FROM all_reps r
LEFT JOIN signs_points s ON r.REP_LDAP = s.REP_LDAP
LEFT JOIN activation_points a ON r.REP_LDAP = a.REP_LDAP
LEFT JOIN double_bonus_points d ON r.REP_LDAP = d.REP_LDAP
LEFT JOIN loan_points l ON r.REP_LDAP = l.REP_LDAP
ORDER BY TOTAL_POINTS DESC;
