"""One canonical view over legacy SARA facts, with explicit provenance.

Never infer transaction identity from equal amounts, or turn a relationship
start into an explicit Birth assertion. Legacy numbered slots are a migration format only; native Catala receives
five lists, with aliases validated and no inactive padding records.
"""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import json
import re
from .schema import WORLD_FAMILIES, WORLD_LIST_TYPES, NO_FACTS

class InputConflict(ValueError):
    """Two encodings disagree about the same underlying fact."""

CLASSIFICATIONS = frozenset({'Government','StateGovernment','ForeignGovernment','EducationalInstitution','Hospital','ReligiousOrganization','MedicalInstitution','PenalInstitution','Student'})


def entity_key(value):
    return (value['kind'], value['id'])


def to_list_world(world: dict) -> dict:
    """Accept native lists or legacy numbered slots; never truncate facts."""
    if not isinstance(world, dict):
        raise InputConflict('World must be an object')
    if set(world) & set(WORLD_LIST_TYPES):
        if set(world) != set(WORLD_LIST_TYPES):
            raise InputConflict('List World requires exactly the five fact-family lists; mixed slot/list inputs are invalid')
        if any(not isinstance(value, list) for value in world.values()):
            raise InputConflict('Every World family must be a list')
        result = deepcopy(world)
    else:
        result = {field: [] for field in WORLD_LIST_TYPES}
        if not world:
            raise InputConflict('World requires five fact-family lists')
        for slot in world:
            match = re.fullmatch(r'(dependency|financial|relationship|employment|status)_([1-9][0-9]*)', slot)
            if not match:
                raise InputConflict(f'Unknown legacy World field: {slot}')
        for family, (field, _) in WORLD_FAMILIES.items():
            slots = sorted((slot for slot in world if slot.startswith(family+'_')), key=lambda slot: int(slot.rsplit('_', 1)[1]))
            result[field] = [deepcopy(world[slot]) for slot in slots]
    result['dependency_candidates'] = [value for value in result['dependency_candidates'] if value['id'] != 0]
    for family, (field, _) in WORLD_FAMILIES.items():
        if family != 'dependency':
            result[field] = [value for value in result[field] if value['kind'] not in NO_FACTS]
    return result


def active_rows(world, family):
    field = WORLD_FAMILIES[family][0]
    return [(f'{field}[{index}]', row) for index, row in enumerate(world[field])]


def _key(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'))


def normalize_world(world: dict) -> dict:
    """Validate aliases and return canonical facts plus a compatible World.

    Duplicate rows with the same identity and kind collapse only when their
    meaningful payloads agree. Different identifiers are not silently merged.
    """
    legacy = to_list_world(world)
    seen = {}; duplicate_slots = []
    duplicate_locations = []
    for family in ('financial','relationship','employment','status'):
        for slot,row in active_rows(legacy,family):
            if row['identifier']['id'] == 0: raise InputConflict(f'{slot}: active fact has absent identity')
            row_key=(family,entity_key(row['identifier']),row['kind'])
            meaningful=deepcopy(row)
            if family=='financial':meaningful['amount']=str(Decimal(str(meaningful['amount'])).normalize())
            for field in ('start','end'):
                if not meaningful[field+'_present']: meaningful[field]=None
            if row_key in seen:
                if seen[row_key][1] != meaningful: raise InputConflict(f'{slot}: conflicting rows for {row_key}')
                duplicate_slots.append(slot)
                duplicate_locations.append((WORLD_FAMILIES[family][0], int(slot.rsplit("[", 1)[1][:-1])))
            else:seen[row_key]=(slot,meaningful)
    # Remove identical repeated rows without changing their multiplicity.
    for field, index in reversed(duplicate_locations):
        legacy[field].pop(index)
    dates={};parents={};siblings={};transactions={};services=[];elections=set()
    def dated(person,row):
        if person['id']==0 or not row['start_present']:return
        key=entity_key(person);date=row['start']
        item=dates.setdefault(key,{'person':person,'date':None,'relationship_starts':[],'evidence':[]})
        if row['kind']=='Birth':
            if item['date'] is not None and item['date'] != date:
                raise InputConflict(f'Conflicting explicit birth dates for {key}: {item["date"]} versus {date}')
            item['date']=date
        elif date not in item['relationship_starts']:
            item['relationship_starts'].append(date)
        item['evidence'].append({'kind':row['kind'],'identifier':row['identifier']})
    for _,row in active_rows(legacy,'relationship'):
        kind=row['kind'];subjects=[row['subject_'+str(i)] for i in range(1,5) if row['subject_'+str(i)]['id']]
        relatives=[row['relative_'+str(i)] for i in range(1,3) if row['relative_'+str(i)]['id']]
        if kind in ('Birth','Son','Daughter'):
            for person in subjects:dated(person,row)
        for subject in subjects:
            for relative in relatives:
                interval=(row['start'] if row['start_present'] else None,row['end'] if row['end_present'] else None)
                if kind in ('Son','Daughter','Father','Mother'):
                    child,parent=(subject,relative) if kind in ('Son','Daughter') else (relative,subject)
                    key=(entity_key(child),entity_key(parent),interval)
                    item=parents.setdefault(key,{'child':child,'parent':parent,'interval':interval,'evidence_kinds':[]})
                    if kind not in item['evidence_kinds']:item['evidence_kinds'].append(kind)
                if kind in ('Sibling','Brother','Sister'):
                    pair=sorted([subject,relative],key=entity_key);key=(entity_key(pair[0]),entity_key(pair[1]),interval)
                    item=siblings.setdefault(key,{'people':pair,'interval':interval,'evidence_kinds':[]})
                    if kind not in item['evidence_kinds']:item['evidence_kinds'].append(kind)
    for _,row in active_rows(legacy,'financial'):
        identity=entity_key(row['identifier'])
        if row['kind']=='Deduction':continue
        recipient=row['agent'] if row['kind']=='Income' else row['patient']
        item=transactions.setdefault(identity,{'identifier':row['identifier'],'recipient':recipient,'amount':str(Decimal(str(row['amount']))),'multiplicity':row['multiplicity'],'start':row['start'] if row['start_present'] else None,'end':row['end'] if row['end_present'] else None,'evidence_kinds':[]})
        signature=(entity_key(recipient),Decimal(str(row['amount'])),row['multiplicity'],row['start'] if row['start_present'] else None,row['end'] if row['end_present'] else None)
        previous=(entity_key(item['recipient']),Decimal(item['amount']),item['multiplicity'],item['start'],item['end'])
        if signature != previous:raise InputConflict(f'Conflicting Income/Payment aliases for transaction {identity}')
        if row['kind'] not in item['evidence_kinds']:item['evidence_kinds'].append(row['kind'])
    for _,row in active_rows(legacy,'employment'):
        if row['kind']!='Service':continue
        tags=set()
        for field in ('purpose_1','purpose_2','location_1','location_2','location_3','location_4'):
            value=row[field].get('Known')
            if value in CLASSIFICATIONS:tags.add(value)
        services.append({'identifier':row['identifier'],'classifications':sorted(tags)})
    for _,row in active_rows(legacy,'status'):
        if row['kind']=='ItemizeDeductions' and row['subject']['id']:elections.add(entity_key(row['subject']))
    return {'format':'sara-canonical-v1','birth_dates':sorted(dates.values(),key=_key),'parent_edges':sorted(parents.values(),key=_key),'sibling_edges':sorted(siblings.values(),key=_key),'transactions':sorted(transactions.values(),key=_key),'services':sorted(services,key=_key),'explicit_itemizers':[list(e) for e in sorted(elections)],'world':legacy,'duplicate_slots_removed':duplicate_slots}
