"""核对 Task 2 跨范围监督、解释覆盖与正文重叠，并生成按新闻分组的实验划分。

从项目根目录运行：python3 ntcir19_fehu-master/docs/2026-11-03_Task2_组会准备/evidence/audit_scope_supervision.py
只读取官方 JSON，输出同目录的审计结果与内部划分，不运行模型、不修改数据。
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypedDict, cast


class Article(TypedDict):
    guid: str
    content: str
    title: str
    actors: tuple[str, ...]
    subevents: tuple[str, ...]


class Value(TypedDict):
    actor: str
    value: str
    direction: str
    explanation: str


class Gold(TypedDict):
    guid: str
    article: tuple[Value, ...]
    subevents: dict[str, tuple[Value, ...]]
    unidentified_empty_rows: int


Label = tuple[str, str, str]


def object_record(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise TypeError(f'{location}: expected a JSON object with string keys')
    return cast(dict[str, object], value)


def array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f'{location}: expected a JSON array')
    return cast(list[object], value)


def string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{location}: expected a non-empty string')
    return value


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalize(text: str) -> str:
    return ' '.join(text.split()).casefold()


def load_articles(path: Path) -> tuple[Article, ...]:
    rows = array(json.loads(path.read_text()), str(path))
    result: list[Article] = []
    for index, item in enumerate(rows):
        row = object_record(item, f'{path}[{index}]')
        guid = string(row['guid'], f'{path}[{index}].guid')
        actors: list[str] = []
        for item in array(row['actors'], f'{guid}.actors'):
            actor = object_record(item, f'{guid}.actor')
            if len(actor) != 1:
                raise ValueError(f'{guid}: expected one name/id in actor record')
            actors.append(string(next(iter(actor.values())), f'{guid}.actor_id'))
        events = tuple(string(object_record(e, guid)['id'], f'{guid}.subevent.id')
                       for e in array(row['subevents'], f'{guid}.subevents'))
        if len(set(actors)) != len(actors) or len(set(events)) != len(events):
            raise ValueError(f'{guid}: duplicate actor or subevent identifiers')
        result.append(Article(guid=guid, content=string(row['content'], guid),
                              title=string(row['title'], guid), actors=tuple(actors), subevents=events))
    if len({row['guid'] for row in result}) != len(result):
        raise ValueError(f'{path}: duplicate GUIDs')
    return tuple(result)


def parse_values(items: object, location: str) -> tuple[Value, ...]:
    result: list[Value] = []
    for item in array(items, location):
        row = object_record(item, location)
        actor = string(row['actor'], f'{location}.actor')
        value = string(row['l1_value'], f'{location}.l1_value')
        direction = string(row['direction'], f'{location}.direction')
        if value not in {str(i) for i in range(54)} or direction not in {'0', '1'}:
            raise ValueError(f'{location}: invalid directed label {value}/{direction}')
        result.append(Value(actor=actor, value=value, direction=direction,
                            explanation=string(row['explanation'], f'{location}.explanation')))
    if len({label(v) for v in result}) != len(result):
        raise ValueError(f'{location}: duplicate directed labels')
    return tuple(result)


def label(value: Value) -> Label:
    return value['actor'], value['value'], value['direction']


def load_gold(path: Path, articles: tuple[Article, ...]) -> tuple[Gold, ...]:
    inputs = {article['guid']: article for article in articles}
    result: list[Gold] = []
    for item in array(json.loads(path.read_text()), str(path)):
        row = object_record(item, str(path))
        guid = string(row['guid'], f'{path}.guid')
        if guid not in inputs:
            raise ValueError(f'{path}: gold GUID {guid} has no input')
        subevents: dict[str, tuple[Value, ...]] = {}
        unidentified_empty_rows = 0
        for item in array(row['subevents_human_values'], guid):
            event = object_record(item, guid)
            # 官方文件含少量空 ID、空标签记录。明确记录这一形状，不猜测它属于哪个事件。
            if event['subevent_id'] == '' and event['subevent_human_values'] == []:
                unidentified_empty_rows += 1
                continue
            sid = string(event['subevent_id'], guid)
            if sid in subevents or sid not in inputs[guid]['subevents']:
                raise ValueError(f'{guid}: duplicate or unknown gold subevent {sid}')
            subevents[sid] = parse_values(event['subevent_human_values'], f'{guid}/{sid}')
        article_values = parse_values(row['article_human_values'], f'{guid}/article')
        for values in (article_values, *subevents.values()):
            if any(v['actor'] not in inputs[guid]['actors'] for v in values):
                raise ValueError(f'{guid}: gold actor missing from input candidates')
        result.append(Gold(guid=guid, article=article_values, subevents=subevents,
                           unidentified_empty_rows=unidentified_empty_rows))
    if len({g['guid'] for g in result}) != len(result) or set(inputs) != {g['guid'] for g in result}:
        raise ValueError(f'{path}: gold/input GUIDs are not a one-to-one match')
    return tuple(result)


def source_groups(articles: tuple[Article, ...]) -> dict[str, tuple[str, ...]]:
    """同正文或同标题形成连通分量；保守分组，不声称排除全部语义近重复。"""
    neighbors: dict[str, set[str]] = {a['guid']: set() for a in articles}
    owners: dict[str, str] = {}
    for article in articles:
        for key in ('body:' + digest(normalize(article['content'])), 'title:' + normalize(article['title'])):
            guid = article['guid']
            if key in owners:
                neighbors[guid].add(owners[key])
                neighbors[owners[key]].add(guid)
            else:
                owners[key] = guid
    remaining = set(neighbors)
    groups: dict[str, tuple[str, ...]] = {}
    while remaining:
        stack = [min(remaining)]
        members: set[str] = set()
        while stack:
            guid = stack.pop()
            if guid in members:
                continue
            members.add(guid)
            stack.extend(neighbors[guid] - members)
        remaining -= members
        groups[digest('\n'.join(sorted(members)))] = tuple(sorted(members))
    return groups


def profile(articles: tuple[Article, ...], gold: tuple[Gold, ...]) -> dict[str, object]:
    inputs = {a['guid']: a for a in articles}
    positives = covered = article_count = article_only = union_count = condition_candidates = dual = 0
    explanations: list[str] = []
    localization: Counter[int] = Counter()
    classes: Counter[str] = Counter()
    violation_examples: list[dict[str, str]] = []
    for row in gold:
        article_labels = {label(v) for v in row['article']}
        occurrences: Counter[Label] = Counter(label(v) for vs in row['subevents'].values() for v in vs)
        positives += sum(occurrences.values())
        covered += sum(n for value, n in occurrences.items() if value in article_labels)
        article_count += len(article_labels)
        article_only += len(article_labels - occurrences.keys())
        union_count += len(occurrences)
        condition_candidates += len(article_labels) * len(inputs[row['guid']]['subevents'])
        localization.update(occurrences.values())
        for value in occurrences.keys() - article_labels:
            violation_examples.append({'guid':row['guid'], 'actor':value[0], 'value':value[1], 'direction':value[2]})
        for values in row['subevents'].values():
            direction_counts = Counter((v['actor'], v['value']) for v in values)
            dual += sum(count == 2 for count in direction_counts.values())
            explanations.extend(v['explanation'] for v in values)
            classes.update(f"{v['direction']}:{v['value']}" for v in values)
    words = sorted(len(text.split()) for text in explanations)
    bodies = Counter(digest(normalize(a['content'])) for a in articles)
    candidates = sum(len(a['actors']) * len(a['subevents']) for a in articles)
    return {
        'records':len(articles), 'unique_normalized_bodies':len(bodies),
        'repeated_body_groups':sum(n > 1 for n in bodies.values()),
        'body_or_title_components':len(source_groups(articles)),
        'candidate_actor_subevent_tuples':candidates,
        'all_108_label_cells':candidates * 108, 'directed_subevent_positives':positives,
        'positive_density_all_cells':positives / (candidates * 108),
        'positives_contained_in_same_actor_article_gold':covered,
        'containment_fraction':covered / positives, 'containment_violations':violation_examples,
        'article_directed_labels':article_count, 'subevent_union_distinct_labels':union_count,
        'article_labels_without_subevent_label':article_only,
        'article_only_fraction':article_only / article_count,
        'gold_article_label_cross_subevent_cells':condition_candidates,
        'gold_article_conditional_density':positives / condition_candidates,
        'positive_subevents_per_article_actor_label_histogram':dict(sorted(localization.items())),
        'same_subevent_actor_value_both_directions':dual,
        'explanations_nonempty':len(explanations), 'explanations_unique':len(set(explanations)),
        'explanation_word_median':statistics.median(words),
        'explanation_word_p95':words[int(len(words) * .95)],
        'observed_directed_classes':len(classes), 'directed_classes_with_lt20_positives':sum(n < 20 for n in classes.values()),
        'unidentified_empty_gold_rows':sum(g['unidentified_empty_rows'] for g in gold),
        'input_subevents_without_addressed_gold_row':sum(len(set(inputs[g['guid']]['subevents']) - g['subevents'].keys()) for g in gold),
    }


def overlap(first: tuple[Article, ...], second: tuple[Article, ...]) -> dict[str, object]:
    first_bodies: dict[str, list[str]] = defaultdict(list)
    for row in first:
        first_bodies[digest(normalize(row['content']))].append(row['guid'])
    matches = [dict(second_guid=row['guid'], first_guids=sorted(first_bodies[digest(normalize(row['content']))]),
                    normalized_body_sha256=digest(normalize(row['content'])), title=row['title'])
               for row in second if digest(normalize(row['content'])) in first_bodies]
    raw_first = {row['content'] for row in first}
    return {'matched_normalized_body_groups':len({m['normalized_body_sha256'] for m in matches}),
            'matched_second_records':len(matches), 'second_record_count':len(second),
            'matched_second_fraction':len(matches) / len(second),
            'raw_exact_matched_second_records':sum(row['content'] in raw_first for row in second),
            'matches':matches}


def split_manifest(articles: tuple[Article, ...], seed: str) -> dict[str, object]:
    groups = source_groups(articles)
    ordered = sorted(groups, key=lambda group: digest(seed + group))
    fit_end, tune_end = int(len(ordered) * .8), int(len(ordered) * .9)
    partitions = {'fit':ordered[:fit_end], 'tune':ordered[fit_end:tune_end], 'holdout':ordered[tune_end:]}
    memberships = {part:sorted(guid for group in group_ids for guid in groups[group])
                   for part, group_ids in partitions.items()}
    if len({guid for guids in memberships.values() for guid in guids}) != len(articles):
        raise ValueError('Internal split lost records or duplicated a GUID')
    article_map = {a['guid']:a for a in articles}
    for first, second in [('fit','tune'),('fit','holdout'),('tune','holdout')]:
        for field in ('content', 'title'):
            a = {normalize(article_map[g][field]) for g in memberships[first]}
            b = {normalize(article_map[g][field]) for g in memberships[second]}
            if a & b:
                raise ValueError(f'Internal {field} overlap between {first} and {second}')
    return {'seed':seed, 'grouping':'Connected components of normalized body equality OR normalized title equality',
            'normalization':'collapse whitespace, then Python str.casefold()',
            'limitation':'Semantic near-duplicates may remain; no model or hyperparameter has been evaluated on this split',
            'component_counts':{p:len(ids) for p,ids in partitions.items()},
            'record_counts':{p:len(ids) for p,ids in memberships.items()},
            'guids':memberships, 'groups':groups}


def main() -> None:
    output = Path(__file__).resolve().parent
    project = output.parents[2]
    paths = {split:project / 'dataset' / split / f'{split}_event_base.json' for split in ('train','dev')}
    paths['test2'] = project / 'dataset/test/test_subevent_event_base.json'
    articles = {split:load_articles(path) for split,path in paths.items()}
    gold_paths = {s:project / 'dataset/gold_labels' / s / f'{s}_human_values.json' for s in ('train','dev')}
    gold = {s:load_gold(path, articles[s]) for s,path in gold_paths.items()}
    evidence = {'status':'Data audit only, no model results', 'date':'2026-11-03',
                'file_sha256':{str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (*paths.values(), *gold_paths.values())},
                'normalization':'collapse whitespace and casefold; punctuation is preserved',
                'profiles':{s:profile(articles[s], gold[s]) for s in ('train','dev')},
                'overlap':{f'{a}__{b}':overlap(articles[a], articles[b])
                           for a,b in [('train','dev'),('train','test2'),('dev','test2')]}}
    manifest = split_manifest(articles['train'], 'fehu-task2-scope-20261103')
    (output / 'scope_supervision_audit.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    (output / 'grouped_train_split.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'profiles':evidence['profiles'], 'split_records':manifest['record_counts'],
                      'split_groups':manifest['component_counts']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
