#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source venv/bin/activate

echo "=== Initializing KB database ==="
kb init

echo ""
echo "=== Setting up user profile ==="
kb setup --name "Test User" --calories 2500 --protein 100

echo ""
echo "=== Adding pantry items ==="
kb add "Chicken Breast" 16 --unit oz
kb add "Broccoli" 2 --unit cup
kb add "Rice (White)" 3 --unit "cup cooked"
kb add "Tomato" 2
kb add "Onion" 1
kb add "Garlic" 4 --unit clove
kb add "Olive Oil" 4 --unit tbsp
kb add "Eggs" 6 --unit "large egg"
kb add "Cheddar Cheese" 4 --unit oz
kb add "Milk" 1 --unit cup

echo ""
echo "=== Pantry contents ==="
kb pantry

echo ""
echo "=== Database location ==="
kb db-path
