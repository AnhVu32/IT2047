#!/usr/bin/env python3
"""
Crawl full details for all listings in batches.
This script crawls detail pages (with full info) in safe batches to avoid anti-bot blocking.
"""
import json
import subprocess
import sys
from pathlib import Path

BATCH_SIZE = 100
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

def run_crawler(batch_num: int, start_offset: int, batch_size: int):
    """Run crawler for one batch and return count of items."""
    output_file = OUTPUT_DIR / f"batch_{batch_num:03d}_listings.json"
    
    cmd = [
        sys.executable,
        "crawler.py",
        "--pages", "529",
        "--max-items", str(batch_size),
        "--format", "json",
        "--output", str(output_file),
        "--include-snippet",
    ]
    
    print(f"\n=== Batch {batch_num} ({start_offset+1}-{start_offset+batch_size}) ===")
    print(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"ERROR: Batch {batch_num} failed")
        return 0
    
    try:
        with output_file.open(encoding='utf-8') as f:
            items = json.load(f)
            count = len(items) if isinstance(items, list) else 0
            print(f"✓ Batch {batch_num} completed: {count} items")
            return count
    except Exception as e:
        print(f"ERROR reading output: {e}")
        return 0


def merge_batches():
    """Merge all batch JSON files into single file."""
    batch_files = sorted(OUTPUT_DIR.glob("batch_*.json"))
    if not batch_files:
        print("No batch files found")
        return
    
    all_items = []
    total = 0
    
    print(f"\n=== Merging {len(batch_files)} batch files ===")
    for batch_file in batch_files:
        try:
            with batch_file.open(encoding='utf-8') as f:
                items = json.load(f)
                if isinstance(items, list):
                    all_items.extend(items)
                    total += len(items)
                    print(f"✓ {batch_file.name}: {len(items)} items")
        except Exception as e:
            print(f"✗ {batch_file.name}: {e}")
    
    merged_file = OUTPUT_DIR / "all_listings_full_detail.json"
    with merged_file.open("w", encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Merged {total} total items -> {merged_file}")
    return merged_file, total


def json_to_xlsx(json_file: Path, xlsx_file: Path):
    """Convert JSON to Excel."""
    try:
        from openpyxl import Workbook
        
        with json_file.open(encoding='utf-8') as f:
            rows = json.load(f)
        
        if not rows:
            print("No rows in JSON")
            return
        
        fieldnames = []
        seen = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
        
        wb = Workbook()
        ws = wb.active
        ws.title = "listings"
        ws.append(fieldnames)
        
        for i, row in enumerate(rows, start=2):
            values = [row.get(k, "") for k in fieldnames]
            ws.append(values)
            if i % 1000 == 0:
                print(f"  {i}/{len(rows)} rows written...")
        
        xlsx_file.parent.mkdir(parents=True, exist_ok=True)
        wb.save(xlsx_file)
        print(f"✓ Converted to Excel: {xlsx_file}")
        
    except Exception as e:
        print(f"ERROR converting to Excel: {e}")


def main():
    import time
    
    print("Crawling full details in batches...")
    print(f"Batch size: {BATCH_SIZE}")
    
    total_crawled = 0
    batch_num = 1
    offset = 0
    
    while offset < 10600:
        count = run_crawler(batch_num, offset, BATCH_SIZE)
        if count == 0:
            print(f"Batch {batch_num} returned 0 items, stopping")
            break
        
        total_crawled += count
        offset += count
        batch_num += 1
        
        if count > 0 and offset < 10600:
            print(f"Waiting 5 seconds before next batch...")
            time.sleep(5)
    
    print(f"\n=== Summary ===")
    print(f"Total crawled: {total_crawled} items in {batch_num-1} batches")
    
    merged_file, merged_count = merge_batches()
    
    if merged_file:
        xlsx_file = OUTPUT_DIR / "all_listings_full_detail.xlsx"
        print(f"\nConverting to Excel...")
        json_to_xlsx(merged_file, xlsx_file)
        
        print(f"\n✓ Done! Files ready:")
        print(f"  - JSON: {merged_file} ({merged_count} items)")
        print(f"  - XLSX: {xlsx_file}")


if __name__ == "__main__":
    main()
