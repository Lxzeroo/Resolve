"""Offline evaluation for deterministic baseline on checked-in labeled examples."""
import csv
from collections import Counter
from pathlib import Path
from app.main import categorize


def evaluate(path: str = 'tests/data/triage_labels.csv') -> dict:
    rows = list(csv.DictReader(Path(path).open(encoding='utf-8', newline='')))
    labels = sorted({r['category'] for r in rows})
    correct = 0
    matrix = Counter()
    for row in rows:
        predicted = categorize(row['subject'], row['body'])[0]
        matrix[(row['category'], predicted)] += 1
        correct += predicted == row['category']
    scores = {}
    for label in labels:
        tp = matrix[(label, label)]
        fp = sum(matrix[(true, label)] for true in labels if true != label)
        fn = sum(matrix[(label, pred)] for pred in labels if pred != label)
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        scores[label] = {'precision': round(precision, 3), 'recall': round(recall, 3),
                         'f1': round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0}
    return {'examples': len(rows), 'accuracy': round(correct / len(rows), 3) if rows else 0,
            'macro_f1': round(sum(s['f1'] for s in scores.values()) / len(scores), 3) if scores else 0,
            'by_category': scores}


if __name__ == '__main__':
    import json
    print(json.dumps(evaluate(), indent=2))
