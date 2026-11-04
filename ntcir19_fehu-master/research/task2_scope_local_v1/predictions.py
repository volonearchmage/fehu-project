"""Strict all-candidate Task 2 export; no gold is accepted here."""
import math


def export_predictions(articles, probabilities, fine_to_coarse, threshold):
    if not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Invalid threshold")
    expected = {(a.guid, aid, e.id) for a in articles for aid, _ in a.actors for e in a.events}
    if set(probabilities) != expected:
        raise ValueError(f"Candidate coverage mismatch: missing={len(expected - probabilities.keys())}, extra={len(probabilities.keys() - expected)}")
    task2a, task2b = [], []
    for a in articles:
        coarse_events, fine_events = [], []
        for event in a.events:
            coarse, fine = set(), []
            for aid, _ in a.actors:
                values = probabilities[(a.guid, aid, event.id)]
                if len(values) != 108 or not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
                    raise ValueError("Expected 108 finite probabilities, including empty predictions")
                for idx, value in enumerate(values):
                    if value >= threshold:
                        vid, direction = str(idx // 2), str(idx % 2)
                        fine.append(dict(actor=aid, l1_value=vid, direction=direction))
                        coarse.add((aid, fine_to_coarse[vid]))
            coarse_events.append(dict(subevent_id=event.id, subevent_human_values=[dict(actor=a, l2_value=v) for a, v in sorted(coarse)]))
            fine_events.append(dict(subevent_id=event.id, subevent_human_values=fine))
        task2a.append(dict(guid=a.guid, subevents_human_values=coarse_events))
        task2b.append(dict(guid=a.guid, subevents_human_values=fine_events))
    return {"task2a": task2a, "task2b": task2b, "coverage": dict(articles=len(articles), events=sum(len(a.events) for a in articles), candidates=len(expected))}
