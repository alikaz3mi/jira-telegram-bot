echo "Example 1: Basic sprint evaluation"
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --dry-run

echo ""

# Example 2: Using sprint name instead of ID
echo "Example 2: Using sprint name"
python scripts/run_team_evaluation.py \
    --sprint-name "Sprint 47" \
    --project-keys "PARSCHAT,PROJ2" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --tab-name "Q4 Team Evaluation" \
    --dry-run

echo ""

# Example 3: Custom work schedule (Mon-Fri, 40 hours)
echo "Example 3: Custom work schedule"
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --weekly-hours 40 \
    --workdays "1,2,3,4,5" \
    --timezone "America/New_York" \
    --dry-run

echo ""

# Example 4: Custom scoring weights
echo "Example 4: Custom scoring weights"
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --score-weights '{"deadline": 0.4, "worklog": 0.3, "high_priority": 0.2, "defects": 0.1}' \
    --defect-thresholds '{"support_per_story": 0.2, "tester_per_story": 0.3, "max_penalty": 50}' \
    --dry-run

echo ""

# Example 5: Verbose mode for debugging
echo "Example 5: Verbose mode"
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --verbose \
    --dry-run

echo ""
echo "Remove --dry-run from any example above to actually write to Google Sheets"
