> **⚠️ HISTORICAL SHEET — superseded in part. Authoritative verdicts are in `vsl_final_labels.csv`.**
>
> This sheet records the *original* generated SQL, expected behaviors, and verdicts. A later
> ground-truth audit (AI-assisted; the authors re-judged the affected cases) found that some original
> expectations and verdicts here were not supportable by the data and were **superseded**. For example,
> a record-counting query was credited for a density intent although the schema provides no denominator
> or area field to normalize by. The audit corrected eight condition-labels across six cases.
>
> **Use the corrected, authoritative labels in `vsl_final_labels.csv`.** Every change from these sheets
> is listed with a reason in `vsl_corrections_log.csv`. The original text below is preserved unchanged
> for traceability.

---

# VSL Human Evaluation Sheet — Information-Matched Prose Ablation (D2, vst_prose)
Generated: 2026-10-16 04:42 UTC
Total cases: 124

Condition: agent + schema + the SAME VST facts PM uses, written as flat natural-language prose,
with NO structured constraints and NO planner enforcement. Tests whether the information in VSTs,
or their operationalization/enforcement, drives the gains.

**Verdict options**: `correct` / `partial` / `incorrect`

---

## Domain: finance

### finance_001 — comparative_grounding (medium)

**Intent**: Loans with unusually high principal amount given their loan status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, status
FROM loan
WHERE amount > (
    SELECT PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY amount)
    FROM loan
    WHERE status = loan.status
)
ORDER BY amount DESC;
```

**D2 Verdict**: `partial`  **Notes**: The inner status = loan.status comparison resolves to the inner table on both sides; the percentile is global rather than status-conditioned.

---

### finance_002 — comparative_grounding (easy)

**Intent**: Find unusually large withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT trans_id, account_id, date, amount
FROM trans
WHERE type = 'debit' AND amount > 20740;
```

**D2 Verdict**: `partial`  **Notes**: Uses a numerical cutoff without showing its distributional derivation. If 20740 is documented as a supplied withdrawal-tail threshold, this could be correct.

---

### finance_003 — process_misinterpretation (medium)

**Intent**: Accounts with sustained negative balance

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### VST-prose SQL
```sql
SELECT DISTINCT t.account_id
FROM trans t
WHERE t.balance < 0
GROUP BY t.account_id
HAVING COUNT(CASE WHEN t.balance >= 0 THEN 1 END) = 0;
```

**D2 Verdict**: `incorrect`  **Notes**: Filtering to negative balances makes the nonnegative count zero automatically; any account with one negative observation qualifies, without sustained or repeated negativity.

---

### finance_004 — comparative_grounding (easy)

**Intent**: Find large loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount > 439769;
```

**D2 Verdict**: `partial`  **Notes**: The constant's distributional provenance is not provided in this sheet. If 439769 is documented as the supplied large-loan threshold, this could be correct.

---

### finance_005 — comparative_grounding (medium)

**Intent**: Accounts with unusually frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT 
    a.account_id, 
    COUNT(t.trans_id) AS withdrawal_count
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'withdrawal'
GROUP BY 
    a.account_id
HAVING 
    COUNT(t.trans_id) > (
        SELECT AVG(withdrawal_count) + 2 * STDDEV(withdrawal_count)
        FROM (
            SELECT COUNT(t2.trans_id) AS withdrawal_count
            FROM trans t2
            WHERE t2.type = 'withdrawal'
            GROUP BY t2.account_id
        ) AS subquery
    );
```

**D2 Verdict**: `correct`  **Notes**: Counts withdrawals per account and uses a distribution-based upper-tail cutoff on those counts; assumes the supplied transaction-type mapping is valid.

---

### finance_006 — role_confusion (hard)

**Intent**: Clients with highest account

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### VST-prose SQL
```sql
SELECT c.client_id, COUNT(a.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 1;
```

**D2 Verdict**: `correct`  **Notes**: Counts associated accounts instead of ranking identifiers, as explicitly permitted.

---

### finance_008 — process_misinterpretation (hard)

**Intent**: Loans with payment irregularity

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE status = 'B' OR status = 'D';
```

**D2 Verdict**: `incorrect`  **Notes**: A static status exclusion does not identify payment irregularity from event history.

---

### finance_009 — comparative_grounding (medium)

**Intent**: Loans with high amount but low repayment

**Expected behavior**: Use relative high/low cutoffs for both amount and repayment.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, payments
FROM loan
WHERE amount > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM loan)
  AND payments < (SELECT PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY payments) FROM loan);
```

**D2 Verdict**: `correct`  **Notes**: Uses relative upper and lower percentile cutoffs for amount and repayment respectively.

---

### finance_010 — quantitative_misinterpretation (medium)

**Intent**: Loans with largest remaining balance

**Expected behavior**: Rank by estimated unpaid balance, not by original loan amount.

#### VST-prose SQL
```sql
SELECT 
    l.loan_id, 
    l.account_id, 
    l.amount - (l.payments * l.duration) AS remaining_balance
FROM 
    loan l
ORDER BY 
    remaining_balance DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Subtracts scheduled payments over the full loan term rather than repayments made so far; this is not current unpaid balance.

---

### finance_011 — role_confusion (medium)

**Intent**: Most important accounts

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### VST-prose SQL
```sql
SELECT 
    a.account_id, 
    SUM(t.amount) AS total_transaction_amount
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
GROUP BY 
    a.account_id
ORDER BY 
    total_transaction_amount DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Transaction volume is a plausible importance proxy, but the intended meaning of importance remains unspecified.

---

### finance_012 — process_misinterpretation (hard)

**Intent**: Accounts with increasing withdrawal frequency over time

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
WITH withdrawal_counts AS (
    SELECT 
        a.account_id,
        t.date,
        COUNT(*) FILTER (WHERE t.type = 'withdrawal') AS withdrawal_count
    FROM 
        account a
    JOIN 
        trans t ON a.account_id = t.account_id
    GROUP BY 
        a.account_id, t.date
),
withdrawal_trend AS (
    SELECT 
        account_id,
        withdrawal_count,
        LAG(withdrawal_count) OVER (PARTITION BY account_id ORDER BY date) AS previous_withdrawal_count
    FROM 
        withdrawal_counts
)
SELECT DISTINCT 
    account_id
FROM 
    withdrawal_trend
WHERE 
    withdrawal_count > previous_withdrawal_count
ORDER BY 
    account_id;
```

**D2 Verdict**: `partial`  **Notes**: Detects an increase between observed dates, but does not establish a sustained frequency trend or include missing dates.

---

### finance_014 — comparative_grounding (hard)

**Intent**: Loans with extreme duration compared to principal

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE duration > 60 AND amount < 10000
ORDER BY duration DESC, amount ASC;
```

**D2 Verdict**: `partial`  **Notes**: Captures long-duration, small-principal loans, but uses fixed cutoffs rather than a distributional or conditional comparison.

---

### finance_015 — quantitative_misinterpretation (medium)

**Intent**: Loans with high repayment ratio

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### VST-prose SQL
```sql
SELECT 
    loan.loan_id, 
    loan.account_id, 
    loan.amount, 
    loan.payments, 
    (loan.payments * loan.duration) / loan.amount AS repayment_ratio
FROM 
    loan
WHERE 
    (loan.payments * loan.duration) / loan.amount > 1
ORDER BY 
    repayment_ratio DESC;
```

**D2 Verdict**: `correct`  **Notes**: Computes scheduled total repayment divided by principal, matching the repayment-ratio operationalization used in the earlier review; assumes nontruncating numeric division.

---

### finance_016 — process_misinterpretation (medium)

**Intent**: Accounts with frequent negative-balance events

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### VST-prose SQL
```sql
SELECT 
    a.account_id, 
    COUNT(t.trans_id) AS negative_balance_events
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.balance < 0
GROUP BY 
    a.account_id
HAVING 
    COUNT(t.trans_id) > 1
ORDER BY 
    negative_balance_events DESC;
```

**D2 Verdict**: `partial`  **Notes**: Counts negative observations, but repeated observations can belong to one negative episode; frequency has no time basis.

---

### finance_021 — comparative_grounding (hard)

**Intent**: Loans that look risky despite having a good status.

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### VST-prose SQL
```sql
SELECT loan.loan_id, loan.account_id, loan.amount, loan.duration, loan.payments, loan.status
FROM loan
WHERE loan.status = 'good' AND loan.amount > 439769;
```

**D2 Verdict**: `partial`  **Notes**: Uses good status and large amount, but no within-status relative threshold; the status mapping and constant provenance need verification.

---

### finance_022 — role_confusion (medium)

**Intent**: Loans with the most active repayment behavior

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### VST-prose SQL
```sql
SELECT 
    l.loan_id, 
    l.account_id, 
    COUNT(t.trans_id) AS transaction_count
FROM 
    loan l
JOIN 
    trans t ON l.account_id = t.account_id
WHERE 
    t.type = 'credit'
GROUP BY 
    l.loan_id, l.account_id
ORDER BY 
    transaction_count DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Counts credits to the loan account as a repayment-activity proxy, without identifying actual repayments attributable to the loan.

---

### finance_023 — comparative_grounding (easy)

**Intent**: Find unusually small loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, date
FROM loan
WHERE amount < (SELECT PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY amount) FROM loan);
```

**D2 Verdict**: `correct`  **Notes**: Uses a lower-tail percentile threshold for loan amount.

---

### finance_024 — process_misinterpretation (hard)

**Intent**: Which accounts recovered from a negative balance?

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### VST-prose SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2 ON t1.account_id = t2.account_id
WHERE t1.balance < 0 AND t2.balance >= 0 AND t1.date < t2.date;
```

**D2 Verdict**: `correct`  **Notes**: Finds a negative balance followed by a later nonnegative balance for the same account.

---

### finance_026 — comparative_grounding (medium)

**Intent**: Clients with high balance but low transaction volume

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, AVG(t.balance) AS average_balance, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
GROUP BY c.client_id, c.gender, c.birth_date
HAVING AVG(t.balance) > (
    SELECT AVG(balance) FROM trans
) AND COUNT(t.trans_id) < (
    SELECT AVG(transaction_count) FROM (
        SELECT COUNT(trans_id) AS transaction_count
        FROM trans
        GROUP BY account_id
    ) AS subquery
)
ORDER BY average_balance DESC, transaction_count ASC;
```

**D2 Verdict**: `partial`  **Notes**: Aggregates by client and uses relative thresholds, but compares client transaction counts with an account-level population and balances with a transaction-weighted global mean.

---

### finance_027 — comparative_grounding (medium)

**Intent**: Find accounts with high net inflow

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT 
    t.account_id, 
    SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
    SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS net_inflow
FROM 
    trans t
GROUP BY 
    t.account_id
HAVING 
    SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
    SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) > 0
ORDER BY 
    net_inflow DESC;
```

**D2 Verdict**: `partial`  **Notes**: Computes net inflow, but positive inflow is not necessarily unusually high inflow.

---

### finance_028 — role_confusion (easy)

**Intent**: Top clients by account_id

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### VST-prose SQL
```sql
SELECT c.client_id, COUNT(a.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 10;
```

**D2 Verdict**: `correct`  **Notes**: Uses account counts rather than identifier magnitude, as permitted by the expected behavior.

---

### finance_030 — comparative_grounding (easy)

**Intent**: Find unusually large loans

**Expected behavior**: Use a distribution-based threshold for unusually large loans instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount > 439769;
```

**D2 Verdict**: `partial`  **Notes**: Uses a fixed numerical cutoff whose distributional provenance is not shown. Could be correct if 439769 is a documented supplied tail threshold.

---

### finance_031 — comparative_grounding (medium)

**Intent**: Find loans much larger than typical for their status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### VST-prose SQL
```sql
SELECT loan_id, account_id, amount, status
FROM loan
WHERE amount > (
    SELECT 1.5 * PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount)
    FROM loan AS l
    WHERE l.status = loan.status
)
ORDER BY amount DESC;
```

**D2 Verdict**: `correct`  **Notes**: Uses a properly correlated within-status percentile with a relative multiplier.

---

### finance_033 — comparative_grounding (hard)

**Intent**: Frequent small incoming transactions

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT account_id, COUNT(*) AS transaction_count
FROM trans
WHERE type = 'credit' AND amount < 1000
GROUP BY account_id
HAVING COUNT(*) > 10
ORDER BY transaction_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Captures repeated small credits, but both size and frequency cutoffs are fixed.

---

### finance_034 — quantitative_misinterpretation (easy)

**Intent**: Compare loan amounts and durations for different loan status

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### VST-prose SQL
```sql
SELECT 
    status,
    AVG(amount) AS average_amount,
    AVG(duration) AS average_duration
FROM 
    loan
GROUP BY 
    status;
```

**D2 Verdict**: `correct`  **Notes**: Compares average amount and duration by status, matching the intent. The generic ratio requirement is inconsistent with that intent.

---

### finance_035 — process_misinterpretation (medium)

**Intent**: Accounts frequently negative

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### VST-prose SQL
```sql
SELECT account_id, COUNT(*) AS negative_balance_count
FROM trans
WHERE balance < 0
GROUP BY account_id
ORDER BY negative_balance_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Ranks negative-balance observation counts, but does not distinguish separate negative episodes or define a time-normalized frequency.

---

### finance_038 — quantitative_misinterpretation (medium)

**Intent**: Find total amount paid back for each loan

**Expected behavior**: Use the metric implied by the question, not a convenient proxy.

#### VST-prose SQL
```sql
SELECT 
    loan.loan_id,
    SUM(trans.amount) AS total_paid_back
FROM 
    loan
JOIN 
    trans ON loan.account_id = trans.account_id
WHERE 
    trans.type = 'credit'
GROUP BY 
    loan.loan_id;
```

**D2 Verdict**: `partial`  **Notes**: Aggregates account credits, but does not establish that they are repayments attributable to each loan.

---

### finance_041 — process_misinterpretation (hard)

**Intent**: Find accounts showing sustained financial distress

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### VST-prose SQL
```sql
SELECT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
GROUP BY a.account_id
HAVING AVG(t.balance) < 0
   AND COUNT(CASE WHEN t.amount < 0 THEN 1 END) > 5
   AND COUNT(CASE WHEN t.amount > 0 THEN 1 END) < 5;
```

**D2 Verdict**: `partial`  **Notes**: Uses average negative balance and transaction-sign counts as distress proxies, but does not establish sustained negative episodes; amount-sign interpretation is unverified.

---

### finance_042 — comparative_grounding (medium)

**Intent**: Large loans per status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### VST-prose SQL
```sql
SELECT status, COUNT(*) AS large_loan_count
FROM loan
WHERE amount > 439769
GROUP BY status;
```

**D2 Verdict**: `partial`  **Notes**: Counts loans above a global numerical cutoff by status rather than identifying relatively large loans within each status.

---

### finance_043 — process_misinterpretation (hard)

**Intent**: Which accounts stayed in negative balance for at least 30 days?

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### VST-prose SQL
```sql
SELECT t.account_id
FROM trans t
WHERE t.balance < 0
GROUP BY t.account_id
HAVING COUNT(DISTINCT t.date) >= 30;
```

**D2 Verdict**: `partial`  **Notes**: Requires negative observations on 30 distinct dates, but these can be nonconsecutive and span recoveries; continuous 30-day negativity is not established.

---

### finance_044 — process_misinterpretation (hard)

**Intent**: Customers with suspicious activity patterns

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### VST-prose SQL
```sql
SELECT DISTINCT c.client_id, c.gender, c.birth_date, d.a2 AS district_name
FROM client c
JOIN disp dp ON c.client_id = dp.client_id
JOIN account a ON dp.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
JOIN district d ON c.district_id = d.district_id
WHERE t.amount > 20740 OR t.balance > 58647
ORDER BY c.client_id;
```

**D2 Verdict**: `incorrect`  **Notes**: Filters individual transactions by amount or balance without modeling suspicious activity patterns over event history.

---

### finance_046 — role_confusion (medium)

**Intent**: Heavy users

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### VST-prose SQL
```sql
SELECT 
    client.client_id, 
    COUNT(trans.trans_id) AS transaction_count, 
    SUM(trans.amount) AS total_amount
FROM 
    client
JOIN 
    disp ON client.client_id = disp.client_id
JOIN 
    account ON disp.account_id = account.account_id
JOIN 
    trans ON account.account_id = trans.account_id
GROUP BY 
    client.client_id
HAVING 
    COUNT(trans.trans_id) > 100 -- Assuming "heavy users" are those with more than 100 transactions
ORDER BY 
    total_amount DESC;
```

**D2 Verdict**: `correct`  **Notes**: Transaction count and amount are meaningful heavy-usage signals; the role rubric permits this plausible operationalization, although the 100-transaction cutoff is heuristic.

---

### finance_047 — comparative_grounding (medium)

**Intent**: Clients with high repayment activity but low account balance

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, a.account_id, AVG(t.amount) AS avg_repayment_amount, AVG(t.balance) AS avg_balance
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'credit' -- Assuming 'credit' indicates repayment activity
GROUP BY c.client_id, c.gender, c.birth_date, a.account_id
HAVING AVG(t.amount) > (SELECT AVG(amount) FROM trans WHERE type = 'credit') -- High repayment activity
   AND AVG(t.balance) < (SELECT AVG(balance) FROM trans) -- Low account balance
ORDER BY avg_repayment_amount DESC, avg_balance ASC;
```

**D2 Verdict**: `partial`  **Notes**: Uses relative amount and balance comparisons, but assumes all credits are repayments and evaluates client-account pairs rather than client-wide repayment activity.

---

### finance_050 — comparative_grounding (medium)

**Intent**: Accounts with large balance and frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT 
    a.account_id, 
    t.balance, 
    COUNT(t.trans_id) AS withdrawal_count
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'withdrawal' AND 
    t.balance > 58647  -- Assuming "large balance" refers to above the 90th percentile
GROUP BY 
    a.account_id, t.balance
HAVING 
    COUNT(t.trans_id) > 1  -- Assuming "frequent" means more than one withdrawal
ORDER BY 
    t.balance DESC;
```

**D2 Verdict**: `partial`  **Notes**: Uses a possibly supplied high-balance cutoff, but groups counts by individual balance value and substitutes more than one observation for unusually frequent withdrawals.

---

### finance_051 — comparative_grounding (medium)

**Intent**: Clients with repeated small incoming transactions across multiple accounts

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### VST-prose SQL
```sql
SELECT c.client_id, COUNT(DISTINCT t.account_id) AS num_accounts
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN trans t ON d.account_id = t.account_id
WHERE t.type = 'credit' AND t.amount < 1000
GROUP BY c.client_id
HAVING COUNT(DISTINCT t.account_id) > 1
```

**D2 Verdict**: `partial`  **Notes**: Captures small credits across multiple accounts, but the size cutoff is fixed and repeat activity within accounts is not established.

---

### finance_053 — process_misinterpretation (hard)

**Intent**: Loans with rapidly worsening repayment behavior

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
SELECT 
    loan.loan_id, 
    loan.account_id, 
    loan.amount, 
    loan.duration, 
    loan.payments, 
    loan.status
FROM 
    loan
WHERE 
    loan.status = 'B'
ORDER BY 
    loan.date DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Static status and date sorting do not measure worsening repayment behavior.

---

### finance_055 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly volatile balances

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
SELECT 
    t.account_id, 
    COUNT(*) AS num_transactions, 
    STDDEV(t.balance) AS balance_volatility
FROM 
    trans t
GROUP BY 
    t.account_id
HAVING 
    COUNT(*) > 1
ORDER BY 
    balance_volatility DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Ranks overall balance volatility rather than testing whether volatility increases over time.

---

### finance_057 — process_misinterpretation (hard)

**Intent**: Accounts with recurring balance oscillation

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### VST-prose SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2 ON t1.account_id = t2.account_id
WHERE t1.trans_id <> t2.trans_id
AND ABS(t1.balance - t2.balance) > 0
ORDER BY t1.account_id;
```

**D2 Verdict**: `incorrect`  **Notes**: Any two unequal balances qualify; there is no transaction ordering, alternating direction, or recurring oscillation.

---

### finance_058 — quantitative_misinterpretation (medium)

**Intent**: Clients with the highest loan repayment efficiency

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### VST-prose SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    l.loan_id,
    l.amount,
    l.duration,
    l.payments,
    (l.payments * l.duration) / l.amount AS repayment_efficiency
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    loan l ON d.account_id = l.account_id
ORDER BY 
    repayment_efficiency DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Computes a scheduled repayment-to-principal ratio, but repayment efficiency is not defined and actual repayment performance is absent.

---

### finance_061 — quantitative_misinterpretation (hard)

**Intent**: Clients with unusually concentrated incoming cash flow

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### VST-prose SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    a.account_id,
    SUM(t.amount) AS total_incoming_amount
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    account a ON d.account_id = a.account_id
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'credit'
GROUP BY 
    c.client_id, c.gender, c.birth_date, a.account_id
HAVING 
    SUM(t.amount) > (
        SELECT 
            0.9 * MAX(total_amount)
        FROM (
            SELECT 
                SUM(amount) AS total_amount
            FROM 
                trans
            WHERE 
                type = 'credit'
            GROUP BY 
                account_id
        ) AS subquery
    )
ORDER BY 
    total_incoming_amount DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Identifies high total inflow relative to the maximum account total, not concentration of incoming cash flow or a concentration ratio.

---

### finance_062 — process_misinterpretation (hard)

**Intent**: Which accounts show worsening balance patterns

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
WITH balance_changes AS (
    SELECT 
        account_id, 
        date, 
        balance,
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM 
        trans
),
worsening_accounts AS (
    SELECT 
        account_id
    FROM 
        balance_changes
    WHERE 
        previous_balance IS NOT NULL AND balance < previous_balance
    GROUP BY 
        account_id
)

SELECT DISTINCT 
    account_id
FROM 
    worsening_accounts;
```

**D2 Verdict**: `partial`  **Notes**: Uses ordered balance decreases, but a single decrease can qualify without a sustained worsening pattern.

---

### finance_065 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly delayed repayment activity

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
SELECT 
    a.account_id,
    COUNT(l.loan_id) AS number_of_loans,
    SUM(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) AS delayed_repayments
FROM 
    account a
JOIN 
    loan l ON a.account_id = l.account_id
GROUP BY 
    a.account_id
HAVING 
    SUM(CASE WHEN l.status = 'D' THEN 1 ELSE 0 END) > 0
ORDER BY 
    delayed_repayments DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Counts static delayed-status loans rather than increasing repayment delays over time.

---

### finance_066 — process_misinterpretation (hard)

**Intent**: Accounts with recurring overdraft cycles

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### VST-prose SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.balance < 0
GROUP BY a.account_id
HAVING COUNT(CASE WHEN t.balance < 0 THEN 1 END) > 1;
```

**D2 Verdict**: `partial`  **Notes**: Finds repeated negative observations, but not distinct overdraft-and-recovery cycles.

---

### finance_067 — process_misinterpretation (hard)

**Intent**: Clients whose transaction activity is accelerating

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### VST-prose SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.date > (SELECT MAX(t2.date) - INTERVAL '1 month' FROM trans t2 WHERE t2.account_id = a.account_id)
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(t.trans_id) > (
    SELECT COUNT(t3.trans_id)
    FROM trans t3
    WHERE t3.account_id = a.account_id
    AND t3.date BETWEEN (SELECT MAX(t4.date) - INTERVAL '2 month' FROM trans t4 WHERE t4.account_id = a.account_id)
    AND (SELECT MAX(t5.date) - INTERVAL '1 month' FROM trans t5 WHERE t5.account_id = a.account_id)
)
ORDER BY transaction_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Attempts a recent-versus-prior activity comparison, but references ungrouped account_id at client scope and does not measure increasing growth rates.

---

### finance_071 — comparative_grounding (hard)

**Intent**: Clients with unusually high debt-to-income ratios

**Expected behavior**: Compute each client's total outstanding loan amount divided by total credited transactions (as income proxy), then identify clients where this ratio is in the upper tail of the cross-client distribution — not clients exceeding a hardcoded threshold like 0.5 or 2.

#### VST-prose SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    SUM(l.amount) AS total_debt,
    d.a11 AS average_salary,
    CASE 
        WHEN d.a11 > 0 THEN SUM(l.amount) / d.a11
        ELSE NULL
    END AS debt_to_income_ratio
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    account a ON d.account_id = a.account_id
JOIN 
    loan l ON a.account_id = l.account_id
JOIN 
    district d ON c.district_id = d.district_id
GROUP BY 
    c.client_id, c.gender, c.birth_date, d.a11
HAVING 
    CASE 
        WHEN d.a11 > 0 THEN SUM(l.amount) / d.a11
        ELSE 0
    END > 1.5
ORDER BY 
    debt_to_income_ratio DESC;
```

**D2 Verdict**: `partial`  **Notes**: Attempts a debt ratio, but uses salary instead of credited income, original principal instead of outstanding debt, and a fixed cutoff; alias d is also declared twice.

---

### finance_072 — comparative_grounding (medium)

**Intent**: Accounts with unusually high overdraft frequency

**Expected behavior**: Count overdraft events (balance < 0) per account, then identify accounts in the upper tail of the overdraft-frequency distribution across all accounts, rather than accounts with more than N overdrafts.

#### VST-prose SQL
```sql
SELECT 
    a.account_id, 
    COUNT(t.trans_id) AS overdraft_count
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.balance < 0
GROUP BY 
    a.account_id
HAVING 
    COUNT(t.trans_id) > (
        SELECT AVG(overdraft_count) + 2 * STDDEV(overdraft_count)
        FROM (
            SELECT COUNT(t2.trans_id) AS overdraft_count
            FROM account a2
            JOIN trans t2 ON a2.account_id = t2.account_id
            WHERE t2.balance < 0
            GROUP BY a2.account_id
        ) AS subquery
    )
ORDER BY 
    overdraft_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Uses an upper-tail overdraft-count threshold, but the reference distribution excludes zero-overdraft accounts despite the all-accounts requirement.

---

### finance_073 — comparative_grounding (hard)

**Intent**: Districts with outlier default rates

**Expected behavior**: Compute default rate per district (loans with status indicating default / total loans), identify districts in the upper tail of the cross-district default-rate distribution, not districts exceeding an arbitrary cutoff like 0.2 or 20%.

#### VST-prose SQL
```sql
SELECT 
    d.district_id,
    COUNT(l.loan_id) AS total_loans,
    SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) AS default_loans,
    (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)) AS default_rate
FROM 
    district d
JOIN 
    account a ON d.district_id = a.district_id
JOIN 
    loan l ON a.account_id = l.account_id
GROUP BY 
    d.district_id
HAVING 
    (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)) > (
        SELECT AVG(default_rate) + 2 * STDDEV(default_rate)
        FROM (
            SELECT 
                (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)) AS default_rate
            FROM 
                district d
            JOIN 
                account a ON d.district_id = a.district_id
            JOIN 
                loan l ON a.account_id = l.account_id
            GROUP BY 
                d.district_id
        ) AS subquery
    );
```

**D2 Verdict**: `partial`  **Notes**: Correct district-rate and outlier structure, but 'default' is not established as a valid status mapping.

---

### finance_074 — process_misinterpretation (hard)

**Intent**: Accounts whose monthly transaction volume dropped sharply

**Expected behavior**: Compute monthly transaction counts per account, then identify accounts showing a consistent declining trend across at least three consecutive months, not accounts where any recent month is lower than any earlier month.

#### VST-prose SQL
```sql
WITH monthly_transaction_volume AS (
    SELECT 
        account_id,
        DATE_TRUNC('month', TO_DATE(date, 'YYYY-MM-DD')) AS month,
        SUM(amount) AS total_volume
    FROM 
        trans
    GROUP BY 
        account_id, DATE_TRUNC('month', TO_DATE(date, 'YYYY-MM-DD'))
),
volume_change AS (
    SELECT 
        account_id,
        month,
        total_volume,
        LAG(total_volume) OVER (PARTITION BY account_id ORDER BY month) AS previous_month_volume
    FROM 
        monthly_transaction_volume
),
sharp_drop_accounts AS (
    SELECT 
        account_id
    FROM 
        volume_change
    WHERE 
        previous_month_volume IS NOT NULL
        AND total_volume < previous_month_volume * 0.5
)
SELECT DISTINCT 
    account_id
FROM 
    sharp_drop_accounts;
```

**D2 Verdict**: `partial`  **Notes**: Detects a one-month drop in transaction amount, not a consistent decline in transaction counts across three consecutive months.

---

### finance_075 — process_misinterpretation (hard)

**Intent**: Clients whose credit card usage is accelerating

**Expected behavior**: Compute card transaction count per client per month, then identify clients where the month-over-month growth rate in transaction volume is consistently positive and increasing, not clients with the highest total card transaction count.

#### VST-prose SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN card ca ON d.disp_id = ca.disp_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE ca.type = 'credit'
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(t.trans_id) > (
    SELECT AVG(transaction_count)
    FROM (
        SELECT COUNT(t2.trans_id) AS transaction_count
        FROM trans t2
        JOIN account a2 ON t2.account_id = a2.account_id
        JOIN disp d2 ON a2.account_id = d2.account_id
        JOIN card ca2 ON d2.disp_id = ca2.disp_id
        WHERE ca2.type = 'credit'
        GROUP BY d2.client_id
    ) AS subquery
)
ORDER BY transaction_count DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Measures total activity on accounts with an assumed card type, without identifying monthly card transactions or acceleration.

---

### finance_076 — process_misinterpretation (hard)

**Intent**: Loans whose repayment pace is slowing

**Expected behavior**: Compute repayment amount per loan per month from transactions, then identify loans where the monthly repayment amount shows a consistent decline over time — a slowing pace — rather than loans with low total payments or a non-current status.

#### VST-prose SQL
```sql
SELECT l.loan_id, l.account_id, l.amount, l.duration, l.payments, l.status
FROM loan l
JOIN trans t ON l.account_id = t.account_id
WHERE t.type = 'debit' AND t.amount < l.payments
GROUP BY l.loan_id, l.account_id, l.amount, l.duration, l.payments, l.status
HAVING COUNT(t.trans_id) > 1
ORDER BY l.loan_id;
```

**D2 Verdict**: `incorrect`  **Notes**: Finds repeated debit transactions below scheduled payment size, not a decline in repayment pace over time.

---

### finance_081 — role_confusion (hard)

**Intent**: Clients with highest financial dependency on loans

**Expected behavior**: Financial dependency should be measured by total outstanding loan amount relative to total account balance (a loan-to-assets ratio), not the raw number of loans. A client with one large loan may be more dependent than one with many small ones.

#### VST-prose SQL
```sql
SELECT 
    c.client_id, 
    SUM(l.amount) AS total_loan_amount
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    loan l ON d.account_id = l.account_id
GROUP BY 
    c.client_id
ORDER BY 
    total_loan_amount DESC
LIMIT 1;
```

**D2 Verdict**: `partial`  **Notes**: Measures loan exposure, but omits outstanding-balance adjustments and the assets denominator.

---

### finance_082 — role_confusion (hard)

**Intent**: Most profitable districts for the bank

**Expected behavior**: Bank profitability per district should reflect revenue signals (loan amounts × duration as an interest income proxy) minus risk signals (default rates), not total transaction volume or client count, which conflates activity with value.

#### VST-prose SQL
```sql
SELECT 
    d.district_id,
    SUM(l.amount) AS total_loan_amount,
    SUM(o.amount) AS total_order_amount,
    SUM(t.amount) AS total_transaction_amount,
    (SUM(l.amount) + SUM(o.amount) + SUM(t.amount)) AS total_profit
FROM 
    district d
LEFT JOIN account a ON d.district_id = a.district_id
LEFT JOIN loan l ON a.account_id = l.account_id
LEFT JOIN "order" o ON a.account_id = o.account_id
LEFT JOIN trans t ON a.account_id = t.account_id
GROUP BY 
    d.district_id
ORDER BY 
    total_profit DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Attempts a financial-value proxy, but sums transaction and order flows as profit, omits duration and default risk, and multiplies sums through one-to-many joins.

---

### finance_083 — role_confusion (hard)

**Intent**: Accounts with the most active savings behavior

**Expected behavior**: Savings behavior should reflect the net growth of account balance over time (consistent positive balance increments), not the total amount of credit transactions, which includes salary inflows and does not account for withdrawals.

#### VST-prose SQL
```sql
SELECT a.account_id, COUNT(t.trans_id) AS transaction_count
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'credit' AND t.operation = 'credit in cash'
GROUP BY a.account_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Counts incoming cash transactions, but does not measure net balance growth or consistency over time.

---

## Domain: public_safety

### public_safety_001 — comparative_grounding (easy)

**Intent**: Extremely severe crashes

**Expected behavior**: Identify crashes whose severity lies in the upper tail of the crash-severity distribution, using measures such as number of persons injured, number of persons killed, or combined severity indicators, rather than using a fixed constant like number_of_persons_injured > 10.

#### VST-prose SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0
   OR number_of_pedestrians_killed > 0
   OR number_of_cyclist_killed > 0
   OR number_of_motorist_killed > 0;
```

**D2 Verdict**: `partial`  **Notes**: Fatality presence is a severity signal, but no distribution-based extreme-severity criterion.

---

### public_safety_002 — comparative_grounding (medium)

**Intent**: Collisions with unusually high fatalities

**Expected behavior**: Identify collisions whose fatality counts lie in the upper tail of the fatality distribution (e.g., extreme outliers), rather than using fixed constants like number_of_persons_killed >= 5 or mixing injury thresholds with fatality-based intent.

#### VST-prose SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > (
    SELECT AVG(number_of_persons_killed) + 2 * STDDEV(number_of_persons_killed)
    FROM crashes
);
```

**D2 Verdict**: `correct`  **Notes**: Uses a distribution-based upper-tail fatality threshold.

---

### public_safety_003 — quantitative_misinterpretation (medium)

**Intent**: Intersections with highest fatality rate

**Expected behavior**: Compute fatality rate per intersection as total fatalities divided by number of collisions (or appropriate exposure), and rank intersections by this rate rather than by total fatalities.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name,
    SUM(number_of_persons_killed) AS total_fatalities,
    COUNT(collision_id) AS total_crashes,
    CAST(SUM(number_of_persons_killed) AS FLOAT) / COUNT(collision_id) AS fatality_rate
FROM 
    crashes
WHERE 
    on_street_name IS NOT NULL AND cross_street_name IS NOT NULL
GROUP BY 
    on_street_name, cross_street_name
ORDER BY 
    fatality_rate DESC
LIMIT 10;
```

**D2 Verdict**: `correct`  **Notes**: Computes fatalities per collision by intersection and ranks by the rate.

---

### public_safety_004 — process_misinterpretation (hard)

**Intent**: Areas where crash severity is worsening

**Expected behavior**: Identify areas where crash severity increases over time, such as rising injury/fatality severity across time windows, rather than ranking areas by total historical severity.

#### VST-prose SQL
```sql
SELECT 
    borough, 
    zip_code, 
    AVG(number_of_persons_injured + number_of_persons_killed) AS avg_severity
FROM 
    crashes
GROUP BY 
    borough, 
    zip_code
ORDER BY 
    avg_severity DESC
LIMIT 10;
```

**D2 Verdict**: `incorrect`  **Notes**: Ranks historical average severity without measuring changes across time windows.

---

### public_safety_008 — quantitative_misinterpretation (medium)

**Intent**: Areas where pedestrian injury risk is highest

**Expected behavior**: Compute pedestrian injury risk per area as a normalized measure (e.g., number of pedestrian injuries divided by number of collisions or probability of injury), and rank areas by this rate rather than raw counts.

#### VST-prose SQL
```sql
SELECT 
    borough, 
    zip_code, 
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured
FROM 
    crashes
GROUP BY 
    borough, 
    zip_code
ORDER BY 
    total_pedestrians_injured DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Uses pedestrian injuries, but omits collision or exposure normalization.

---

### public_safety_010 — process_misinterpretation (medium)

**Intent**: Increasing collision trend over time

**Expected behavior**: Identify whether collision counts are increasing over time (e.g., rising trend across time windows such as months or years), rather than simply returning counts per date without analyzing the trend direction.

#### VST-prose SQL
```sql
SELECT 
    crash_date, 
    COUNT(collision_id) AS total_collisions
FROM 
    crashes
GROUP BY 
    crash_date
ORDER BY 
    crash_date;
```

**D2 Verdict**: `partial`  **Notes**: Produces a chronological count series, but does not evaluate trend direction.

---

### public_safety_011 — comparative_grounding (medium)

**Intent**: Vehicles involved in extreme-impact collisions

**Expected behavior**: Identify collisions whose impact (e.g., fatalities, injuries, or combined severity) lies in the upper tail of the severity distribution, and then extract associated vehicle types, rather than using fixed constants like number_of_persons_killed >= 5 or number_of_persons_injured >= 40.

#### VST-prose SQL
```sql
SELECT DISTINCT vehicle_type_code_1, vehicle_type_code_2, vehicle_type_code_3
FROM crashes
WHERE number_of_persons_killed > 0
   OR number_of_pedestrians_killed > 0
   OR number_of_cyclist_killed > 0
   OR number_of_motorist_killed > 0;
```

**D2 Verdict**: `partial`  **Notes**: Returns vehicles from fatal crashes, but does not establish extreme impact relative to the severity distribution.

---

### public_safety_016 — process_misinterpretation (medium)

**Intent**: Vehicle types with increasing crash involvement

**Expected behavior**: Identify vehicle types whose crash involvement increases over time (e.g., rising counts across time windows such as months or years), rather than simply counting total crashes per vehicle type and sorting.

#### VST-prose SQL
```sql
WITH yearly_crash_counts AS (
    SELECT
        EXTRACT(YEAR FROM TO_DATE(crash_date, 'YYYY-MM-DD')) AS year,
        vehicle_type_code_1 AS vehicle_type,
        COUNT(*) AS crash_count
    FROM
        crashes
    WHERE
        vehicle_type_code_1 IS NOT NULL
    GROUP BY
        year, vehicle_type
    UNION ALL
    SELECT
        EXTRACT(YEAR FROM TO_DATE(crash_date, 'YYYY-MM-DD')) AS year,
        vehicle_type_code_2 AS vehicle_type,
        COUNT(*) AS crash_count
    FROM
        crashes
    WHERE
        vehicle_type_code_2 IS NOT NULL
    GROUP BY
        year, vehicle_type
    UNION ALL
    SELECT
        EXTRACT(YEAR FROM TO_DATE(crash_date, 'YYYY-MM-DD')) AS year,
        vehicle_type_code_3 AS vehicle_type,
        COUNT(*) AS crash_count
    FROM
        crashes
    WHERE
        vehicle_type_code_3 IS NOT NULL
    GROUP BY
        year, vehicle_type
),
yearly_increase AS (
    SELECT
        vehicle_type,
        year,
        crash_count,
        LAG(crash_count) OVER (PARTITION BY vehicle_type ORDER BY year) AS previous_year_count
    FROM
        yearly_crash_counts
),
increasing_vehicle_types AS (
    SELECT DISTINCT
        vehicle_type
    FROM
        yearly_increase
    WHERE
        crash_count > previous_year_count
)

SELECT
    vehicle_type
FROM
    increasing_vehicle_types
ORDER BY
    vehicle_type;
```

**D2 Verdict**: `partial`  **Notes**: Attempts year-over-year involvement comparisons, but does not combine vehicle-slot counts before LAG, so rows from the same year can be compared as if they were successive years.

---

### public_safety_018 — comparative_grounding (easy)

**Intent**: Collisions with unusually high injuries

**Expected behavior**: Identify collisions whose number of persons injured lies in the upper tail of the injury distribution (e.g., top quantile or statistical outliers), rather than using a fixed constant threshold.

#### VST-prose SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_injured > 1
   OR number_of_pedestrians_injured > 1
   OR number_of_cyclist_injured > 1
   OR number_of_motorist_injured > 1;
```

**D2 Verdict**: `partial`  **Notes**: Uses fixed injury cutoffs rather than a distribution-based upper-tail criterion.

---

### public_safety_019 — comparative_grounding (medium)

**Intent**: Crashes with unusually high combined severity

**Expected behavior**: Compute a combined severity measure using injuries and fatalities, and identify crashes in the upper tail of this severity distribution (e.g., top quantile or outliers), rather than using a fixed constant threshold like > 10.

#### VST-prose SQL
```sql
SELECT 
    collision_id, 
    crash_date, 
    crash_time, 
    borough, 
    zip_code, 
    number_of_persons_injured, 
    number_of_persons_killed, 
    number_of_pedestrians_injured, 
    number_of_pedestrians_killed, 
    number_of_cyclist_injured, 
    number_of_cyclist_killed, 
    number_of_motorist_injured, 
    number_of_motorist_killed
FROM 
    crashes
WHERE 
    (number_of_persons_injured + 
     number_of_persons_killed + 
     number_of_pedestrians_injured + 
     number_of_pedestrians_killed + 
     number_of_cyclist_injured + 
     number_of_cyclist_killed + 
     number_of_motorist_injured + 
     number_of_motorist_killed) > 5;
```

**D2 Verdict**: `partial`  **Notes**: Uses a fixed combined-severity cutoff and adds person totals to their pedestrian/cyclist/motorist components, potentially double-counting casualties.

---

### public_safety_022 — process_misinterpretation (hard)

**Intent**: Find locations with sustained high injury collisions over time

**Expected behavior**: Identify locations where injury-related collisions remain consistently high over time (e.g., persistently high counts across multiple time windows or sustained upward trends), rather than filtering locations with more than a fixed number of injury collisions.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    COUNT(collision_id) AS total_collisions,
    SUM(number_of_persons_injured) AS total_injuries
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    SUM(number_of_persons_injured) > 10
ORDER BY 
    total_injuries DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: Uses all-time count and injury thresholds without persistence across time windows.

---

### public_safety_027 — quantitative_misinterpretation (medium)

**Intent**: Find boroughs with high pedestrian injury rates

**Expected behavior**: Compute pedestrian injury rate per borough as the number of pedestrian injuries divided by the number of collisions, and identify boroughs with high rates rather than using total injury counts.

#### VST-prose SQL
```sql
SELECT borough, 
       SUM(number_of_pedestrians_injured) AS total_pedestrians_injured, 
       COUNT(collision_id) AS total_crashes,
       CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / COUNT(collision_id) AS pedestrian_injury_rate
FROM crashes
WHERE borough IS NOT NULL
GROUP BY borough
ORDER BY pedestrian_injury_rate DESC;
```

**D2 Verdict**: `correct`  **Notes**: Computes pedestrian injuries per collision by borough and ranks by the rate.

---

### public_safety_029 — process_misinterpretation (medium)

**Intent**: Locations with persistent crash patterns

**Expected behavior**: Identify locations where crashes persist over time, such as recurring crashes across multiple time windows or sustained patterns, rather than selecting locations with more than one crash overall.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    COUNT(collision_id) AS crash_count
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    COUNT(collision_id) > 1
ORDER BY 
    crash_count DESC;
```

**D2 Verdict**: `incorrect`  **Notes**: More than one historical crash does not establish persistence across time windows.

---

### public_safety_031 — process_misinterpretation (hard)

**Intent**: Intersections with sustained high injury rates

**Expected behavior**: Identify intersections where injury rates remain consistently high over time (e.g., high injuries per collision across multiple time windows), rather than using a total injury count threshold.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name,
    SUM(number_of_persons_injured) AS total_injuries,
    COUNT(collision_id) AS total_crashes,
    CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) AS average_injuries_per_crash
FROM 
    crashes
WHERE 
    on_street_name IS NOT NULL AND cross_street_name IS NOT NULL
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    COUNT(collision_id) > 10 AND -- Assuming "sustained" means more than 10 crashes
    CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) > 1 -- High injury rate
ORDER BY 
    average_injuries_per_crash DESC;
```

**D2 Verdict**: `partial`  **Notes**: Computes injuries per crash, but substitutes all-time count and rate thresholds for persistence across time windows.

---

### public_safety_032 — process_misinterpretation (hard)

**Intent**: Find areas where commercial vehicles consistently account for the majority of severe collisions

**Expected behavior**: Identify areas where commercial vehicles account for the majority of severe collisions across multiple time windows, rather than only filtering commercial-vehicle collisions or counting them overall.

#### VST-prose SQL
```sql
SELECT 
    borough, 
    zip_code, 
    COUNT(collision_id) AS total_collisions,
    SUM(CASE WHEN vehicle_type_code_1 = 'Commercial Vehicle' OR vehicle_type_code_2 = 'Commercial Vehicle' OR vehicle_type_code_3 = 'Commercial Vehicle' THEN 1 ELSE 0 END) AS commercial_vehicle_collisions
FROM 
    crashes
WHERE 
    number_of_persons_killed > 0 OR 
    number_of_persons_injured > 2
GROUP BY 
    borough, 
    zip_code
HAVING 
    SUM(CASE WHEN vehicle_type_code_1 = 'Commercial Vehicle' OR vehicle_type_code_2 = 'Commercial Vehicle' OR vehicle_type_code_3 = 'Commercial Vehicle' THEN 1 ELSE 0 END) > (total_collisions / 2)
ORDER BY 
    commercial_vehicle_collisions DESC;
```

**D2 Verdict**: `partial`  **Notes**: Tests commercial vehicles' majority share among severe crashes overall, but not across multiple windows; vehicle labels and HAVING alias support need verification.

---

### public_safety_033 — comparative_grounding (easy)

**Intent**: Find severe crashes

**Expected behavior**: Identify crashes whose severity (e.g., based on injuries, fatalities, or combined severity measures) lies in the upper portion of the severity distribution, rather than using a fixed constant threshold.

#### VST-prose SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0
   OR number_of_persons_injured > 5
   OR number_of_pedestrians_killed > 0
   OR number_of_pedestrians_injured > 5
   OR number_of_cyclist_killed > 0
   OR number_of_cyclist_injured > 5
   OR number_of_motorist_killed > 0
   OR number_of_motorist_injured > 5;
```

**D2 Verdict**: `partial`  **Notes**: Uses meaningful severity indicators, but fixed cutoffs.

---

### public_safety_037 — process_misinterpretation (hard)

**Intent**: Areas with worsening pedestrian injury trends

**Expected behavior**: Identify areas where pedestrian injuries increase over successive time windows, rather than ranking areas by aggregate injury counts.

#### VST-prose SQL
```sql
WITH monthly_pedestrian_injuries AS (
    SELECT
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS month,
        borough,
        SUM(number_of_pedestrians_injured) AS total_pedestrian_injuries
    FROM
        crashes
    GROUP BY
        month, borough
),
injury_trends AS (
    SELECT
        borough,
        month,
        total_pedestrian_injuries,
        LAG(total_pedestrian_injuries) OVER (PARTITION BY borough ORDER BY month) AS previous_month_injuries
    FROM
        monthly_pedestrian_injuries
),
worsening_trends AS (
    SELECT
        borough,
        COUNT(*) AS worsening_months
    FROM
        injury_trends
    WHERE
        total_pedestrian_injuries > previous_month_injuries
    GROUP BY
        borough
)
SELECT
    borough
FROM
    worsening_trends
WHERE
    worsening_months > 0
ORDER BY
    worsening_months DESC;
```

**D2 Verdict**: `partial`  **Notes**: Detects monthly increases, but isolated increases can qualify without a sustained worsening trend.

---

### public_safety_038 — process_misinterpretation (hard)

**Intent**: Vehicle types with recurring severe crash involvement

**Expected behavior**: Identify vehicle types repeatedly involved in severe crashes across time periods, rather than ranking vehicle types using only total severe crash counts.

#### VST-prose SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       COUNT(collision_id) AS severe_crash_count
FROM crashes
WHERE number_of_persons_killed > 0 OR number_of_persons_injured > 5
GROUP BY vehicle_type_code_1
HAVING COUNT(collision_id) > 1
ORDER BY severe_crash_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Captures repeated severe involvement, but does not establish recurrence across distinct time periods.

---

### public_safety_040 — role_confusion (medium)

**Intent**: Areas with the most dangerous crash patterns

**Expected behavior**: Interpret danger using meaningful measures such as fatalities, injuries, or severity-weighted crash metrics, rather than ranking areas solely by collision frequency.

#### VST-prose SQL
```sql
SELECT 
    borough,
    zip_code,
    SUM(number_of_persons_injured) AS total_persons_injured,
    SUM(number_of_persons_killed) AS total_persons_killed,
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed,
    SUM(number_of_cyclist_injured) AS total_cyclists_injured,
    SUM(number_of_cyclist_killed) AS total_cyclists_killed,
    SUM(number_of_motorist_injured) AS total_motorists_injured,
    SUM(number_of_motorist_killed) AS total_motorists_killed
FROM 
    crashes
GROUP BY 
    borough, zip_code
ORDER BY 
    total_persons_injured DESC,
    total_persons_killed DESC,
    total_pedestrians_injured DESC,
    total_pedestrians_killed DESC,
    total_cyclists_injured DESC,
    total_cyclists_killed DESC,
    total_motorists_injured DESC,
    total_motorists_killed DESC
LIMIT 10;
```

**D2 Verdict**: `correct`  **Notes**: Uses fatalities and injuries to rank danger, as permitted by the expected behavior.

---

### public_safety_042 — comparative_grounding (medium)

**Intent**: Locations with unusually severe pedestrian crashes

**Expected behavior**: Identify pedestrian crashes whose severity lies in the upper tail of the pedestrian crash severity distribution and return the associated locations.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    SUM(number_of_pedestrians_injured) > 1 OR 
    SUM(number_of_pedestrians_killed) > 0
ORDER BY 
    total_pedestrians_killed DESC, 
    total_pedestrians_injured DESC;
```

**D2 Verdict**: `partial`  **Notes**: Uses pedestrian harm by location, but aggregates totals instead of selecting unusually severe individual pedestrian crashes.

---

### public_safety_046 — comparative_grounding (medium)

**Intent**: Time slots with unusually high crash frequency

**Expected behavior**: Aggregate crash counts by crash_time hour-of-day, then identify hours in the upper tail of the hour-level crash-count distribution, rather than flagging any hour with more than N crashes.

#### VST-prose SQL
```sql
SELECT crash_time, COUNT(collision_id) AS crash_count
FROM crashes
GROUP BY crash_time
HAVING COUNT(collision_id) > (
    SELECT AVG(crash_count) + 2 * STDDEV(crash_count)
    FROM (
        SELECT COUNT(collision_id) AS crash_count
        FROM crashes
        GROUP BY crash_time
    ) AS subquery
)
ORDER BY crash_count DESC;
```

**D2 Verdict**: `partial`  **Notes**: Applies a distribution-based crash-count cutoff, but groups raw crash_time instead of extracting hour-of-day; could be correct if crash_time already stores hour bins.

---

### public_safety_047 — comparative_grounding (medium)

**Intent**: Vehicle types involved in unusually severe crashes

**Expected behavior**: Compute average severity (persons injured + killed) per crash by vehicle type, then identify vehicle types where this severity measure is in the upper tail of the cross-vehicle-type distribution, not those exceeding a fixed injury threshold.

#### VST-prose SQL
```sql
SELECT 
    vehicle_type_code_1, 
    vehicle_type_code_2, 
    vehicle_type_code_3
FROM 
    crashes
WHERE 
    number_of_persons_killed > 0 OR
    number_of_persons_injured > 5
GROUP BY 
    vehicle_type_code_1, 
    vehicle_type_code_2, 
    vehicle_type_code_3
HAVING 
    COUNT(collision_id) > 1
ORDER BY 
    COUNT(collision_id) DESC;
```

**D2 Verdict**: `partial`  **Notes**: Counts severe crashes by vehicle-type combination, rather than average severity per individual vehicle type and upper-tail comparison across types.

---

### public_safety_048 — comparative_grounding (easy)

**Intent**: ZIP codes with outlier crash densities

**Expected behavior**: Count crashes per zip_code and identify ZIP codes in the upper tail of the crash-count distribution across all ZIP codes, not ZIP codes exceeding a hardcoded threshold.

#### VST-prose SQL
```sql
WITH crash_counts AS (
    SELECT 
        zip_code, 
        COUNT(collision_id) AS crash_count
    FROM 
        crashes
    WHERE 
        zip_code IS NOT NULL
    GROUP BY 
        zip_code
),
stats AS (
    SELECT 
        AVG(crash_count) AS avg_crash_count,
        STDDEV(crash_count) AS stddev_crash_count
    FROM 
        crash_counts
)
SELECT 
    cc.zip_code
FROM 
    crash_counts cc
CROSS JOIN 
    stats
WHERE 
    cc.crash_count > (stats.avg_crash_count + 2 * stats.stddev_crash_count)
    OR cc.crash_count < (stats.avg_crash_count - 2 * stats.stddev_crash_count);
```

**D2 Verdict**: `partial`  **Notes**: Correct count-distribution structure, but includes lower-tail ZIP codes when only the upper tail is required.

---

### public_safety_049 — comparative_grounding (hard)

**Intent**: Hours of day with unusually high pedestrian fatality risk

**Expected behavior**: Compute pedestrian fatality rate per hour (pedestrian killed / crashes in that hour) and identify hours in the upper tail of this rate distribution, not hours with fatalities exceeding a fixed count or falling in a manually specified time window.

#### VST-prose SQL
```sql
SELECT 
    crash_time, 
    SUM(number_of_pedestrians_killed) AS total_pedestrian_fatalities
FROM 
    crashes
GROUP BY 
    crash_time
HAVING 
    SUM(number_of_pedestrians_killed) > (
        SELECT AVG(total_pedestrian_fatalities) + 2 * STDDEV(total_pedestrian_fatalities)
        FROM (
            SELECT 
                crash_time, 
                SUM(number_of_pedestrians_killed) AS total_pedestrian_fatalities
            FROM 
                crashes
            GROUP BY 
                crash_time
        ) AS subquery
    )
ORDER BY 
    total_pedestrian_fatalities DESC;
```

**D2 Verdict**: `partial`  **Notes**: Uses a distributional cutoff on pedestrian fatality totals, but omits crashes as denominator and hour-of-day extraction.

---

### public_safety_050 — process_misinterpretation (hard)

**Intent**: Streets with persistently recurring severe crashes across years

**Expected behavior**: Identify streets (on_street_name) that appear in the upper severity tier in multiple distinct years — demonstrating structural danger, not just a one-time spike — rather than streets with the highest all-time aggregate crash count.

#### VST-prose SQL
```sql
SELECT 
    on_street_name, 
    COUNT(collision_id) AS total_crashes,
    SUM(number_of_persons_killed) AS total_killed,
    SUM(number_of_persons_injured) AS total_injured
FROM 
    crashes
WHERE 
    number_of_persons_killed > 0 OR number_of_persons_injured > 5
GROUP BY 
    on_street_name
HAVING 
    COUNT(DISTINCT strftime('%Y', crash_date)) > 1
ORDER BY 
    total_crashes DESC, total_killed DESC, total_injured DESC;
```

**D2 Verdict**: `partial`  **Notes**: Requires severe crashes in multiple years, but not upper-tier street severity within each year.

---

### public_safety_051 — process_misinterpretation (hard)

**Intent**: Boroughs with accelerating cyclist injury rates

**Expected behavior**: Compute cyclist injury rate (cyclists injured per crash) per borough per year, then identify boroughs where this rate is consistently increasing across multiple consecutive years, not boroughs with the highest total cyclist injury count.

#### VST-prose SQL
```sql
WITH monthly_cyclist_injuries AS (
    SELECT
        borough,
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS month,
        SUM(number_of_cyclist_injured) AS total_cyclist_injuries
    FROM
        crashes
    WHERE
        borough IS NOT NULL
    GROUP BY
        borough, DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD'))
),
monthly_injury_growth AS (
    SELECT
        borough,
        month,
        total_cyclist_injuries,
        LAG(total_cyclist_injuries) OVER (PARTITION BY borough ORDER BY month) AS previous_month_injuries
    FROM
        monthly_cyclist_injuries
),
accelerating_boroughs AS (
    SELECT
        borough
    FROM
        monthly_injury_growth
    WHERE
        previous_month_injuries IS NOT NULL
        AND total_cyclist_injuries > previous_month_injuries
    GROUP BY
        borough
    HAVING
        COUNT(*) > 1
)

SELECT DISTINCT borough
FROM accelerating_boroughs;
```

**D2 Verdict**: `partial`  **Notes**: Detects monthly injury-count increases, but omits annual rates and consistent increases across consecutive years.

---

### public_safety_052 — process_misinterpretation (hard)

**Intent**: Contributing factors with increasing crash prevalence over time

**Expected behavior**: Compute the share of crashes attributed to each contributing factor per year, and identify factors where this share consistently increases across multiple years, not factors with the highest total occurrence count.

#### VST-prose SQL
```sql
WITH monthly_crashes AS (
    SELECT
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS crash_month,
        contributing_factor_vehicle_1 AS contributing_factor
    FROM
        crashes
    UNION ALL
    SELECT
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS crash_month,
        contributing_factor_vehicle_2 AS contributing_factor
    FROM
        crashes
    UNION ALL
    SELECT
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS crash_month,
        contributing_factor_vehicle_3 AS contributing_factor
    FROM
        crashes
),
factor_trends AS (
    SELECT
        crash_month,
        contributing_factor,
        COUNT(*) AS crash_count
    FROM
        monthly_crashes
    WHERE
        contributing_factor IS NOT NULL
    GROUP BY
        crash_month, contributing_factor
),
factor_growth AS (
    SELECT
        contributing_factor,
        crash_count,
        LAG(crash_count) OVER (PARTITION BY contributing_factor ORDER BY crash_month) AS previous_crash_count
    FROM
        factor_trends
)
SELECT
    contributing_factor,
    COUNT(*) AS months_with_increase
FROM
    factor_growth
WHERE
    previous_crash_count IS NOT NULL AND
    crash_count > previous_crash_count
GROUP BY
    contributing_factor
ORDER BY
    months_with_increase DESC;
```

**D2 Verdict**: `partial`  **Notes**: Counts monthly increases in factor occurrences, but omits annual crash shares and consistent consecutive increases; factor slots may duplicate crashes.

---

### public_safety_053 — quantitative_misinterpretation (medium)

**Intent**: Vehicle types with highest injury rate per crash involvement

**Expected behavior**: Compute average total persons injured per crash for crashes involving each vehicle type, then rank vehicle types by this per-crash rate, not by the raw total injury count across all crashes involving that type.

#### VST-prose SQL
```sql
SELECT 
    vehicle_type_code_1 AS vehicle_type,
    CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) AS injury_rate
FROM 
    crashes
WHERE 
    vehicle_type_code_1 IS NOT NULL
GROUP BY 
    vehicle_type_code_1
ORDER BY 
    injury_rate DESC
LIMIT 1;
```

**D2 Verdict**: `partial`  **Notes**: Computes the right injury-rate form for the first vehicle slot, but omits crashes where the vehicle type appears only in other slots.

---

### public_safety_054 — quantitative_misinterpretation (medium)

**Intent**: Contributing factors with highest lethality ratio

**Expected behavior**: Compute the lethality ratio as number_of_persons_killed / (number_of_persons_killed + number_of_persons_injured) per contributing factor, then rank by this ratio. Factors in fewer but more lethal crashes would otherwise be obscured by high-frequency low-lethality ones.

#### VST-prose SQL
```sql
SELECT 
    contributing_factor,
    SUM(number_of_persons_killed) AS total_killed,
    SUM(number_of_persons_injured) AS total_injured,
    CASE 
        WHEN SUM(number_of_persons_injured) = 0 THEN NULL
        ELSE CAST(SUM(number_of_persons_killed) AS FLOAT) / SUM(number_of_persons_injured)
    END AS lethality_ratio
FROM (
    SELECT contributing_factor_vehicle_1 AS contributing_factor, number_of_persons_killed, number_of_persons_injured
    FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_2 AS contributing_factor, number_of_persons_killed, number_of_persons_injured
    FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_3 AS contributing_factor, number_of_persons_killed, number_of_persons_injured
    FROM crashes
) AS factors
WHERE contributing_factor IS NOT NULL
GROUP BY contributing_factor
ORDER BY lethality_ratio DESC
LIMIT 1;
```

**D2 Verdict**: `partial`  **Notes**: Uses killed/injured instead of killed/(killed + injured), excludes fatal-only groups, and may duplicate crashes across factor slots; NULL ordering is also unspecified.

---

### public_safety_055 — quantitative_misinterpretation (medium)

**Intent**: Time slots with highest pedestrian-to-motorist injury ratio

**Expected behavior**: Compute the ratio of total pedestrian injuries to total motorist injuries per hour of day, and rank hours by this ratio to identify when pedestrians bear a disproportionate share of injury risk relative to motorists.

#### VST-prose SQL
```sql
SELECT 
    crash_time,
    SUM(number_of_pedestrians_injured) / NULLIF(SUM(number_of_motorist_injured), 0) AS pedestrian_to_motorist_injury_ratio
FROM 
    crashes
GROUP BY 
    crash_time
ORDER BY 
    pedestrian_to_motorist_injury_ratio DESC
LIMIT 1;
```

**D2 Verdict**: `partial`  **Notes**: Uses the intended ratio form, but groups raw time instead of hour-of-day; integer division and NULL ordering may also affect ranking.

---

### public_safety_060 — role_confusion (medium)

**Intent**: Boroughs with worst pedestrian safety record

**Expected behavior**: Pedestrian safety should be measured by pedestrian injuries per crash (or per unit of exposure), not total pedestrian injury count. Boroughs with more crashes would otherwise rank worst purely because of volume, masking genuine rate differences.

#### VST-prose SQL
```sql
SELECT 
    borough, 
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured, 
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM 
    crashes
GROUP BY 
    borough
ORDER BY 
    total_pedestrians_killed DESC, 
    total_pedestrians_injured DESC;
```

**D2 Verdict**: `partial`  **Notes**: Uses pedestrian harm totals, but omits per-crash or exposure normalization.

---

### public_safety_061 — role_confusion (medium)

**Intent**: Streets with most dangerous conditions

**Expected behavior**: Street danger should reflect injury or fatality rate per crash on that street, not raw collision count. A busy intersection with many low-severity crashes is less dangerous than one with fewer but consistently severe crashes.

#### VST-prose SQL
```sql
SELECT on_street_name, 
       SUM(number_of_persons_injured + number_of_persons_killed) AS total_casualties
FROM crashes
GROUP BY on_street_name
ORDER BY total_casualties DESC
LIMIT 10;
```

**D2 Verdict**: `partial`  **Notes**: Uses street casualty totals, but omits the collision denominator.

---

### public_safety_062 — role_confusion (medium)

**Intent**: Vehicle types most responsible for cyclist injuries

**Expected behavior**: Responsibility for cyclist injuries should be measured by the average number of cyclists injured per crash where the vehicle type appears, not the total number of crashes or total cyclist injuries — common vehicle types would otherwise dominate by volume.

#### VST-prose SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       SUM(number_of_cyclist_injured) AS total_cyclist_injuries
FROM crashes
GROUP BY vehicle_type_code_1
ORDER BY total_cyclist_injuries DESC
LIMIT 1;
```

**D2 Verdict**: `partial`  **Notes**: Uses cyclist injury totals from only the first vehicle slot, without per-crash normalization.

---
