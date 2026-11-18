"""Read and render the restricted literal syntax used by SARA's protected tests.

This is a data reader, not an evaluator: scopes, calls, and expressions are rejected.
"""
from __future__ import annotations
import re
from .schema import WORLD_LIST_TYPES

TOKEN = re.compile(r'\s*(--|\|\d{4}-\d{2}-\d{2}\||-?\d+(?:\.\d+)?|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|[{}():\[\];])')


def parse_literal(text: str):
    tokens = []
    pos = 0
    while text[pos:].strip():
        match = TOKEN.match(text, pos)
        if not match:
            raise ValueError(f"Unsupported literal near {text[pos:pos+50]!r}")
        tokens.append(match[1]); pos = match.end()
    index = 0
    def take(expected=None):
        nonlocal index
        value = tokens[index]; index += 1
        if expected is not None and value != expected:
            raise ValueError(f"Expected {expected}, got {value}")
        return value
    def value():
        token = take()
        if token == '[':
            result = []
            while tokens[index] != ']':
                result.append(value())
                if tokens[index] == ']': break
                take(';')
            take(']'); return result
        if token == '(':
            if tokens[index] == 'money':
                take('money'); take('of'); result = take()
            else:
                result = value()
            take(')'); return result
        if token.startswith('|'): return token[1:-1]
        if token in ('true', 'false'): return token == 'true'
        if re.fullmatch(r'-?\d+', token): return int(token)
        if index < len(tokens) and tokens[index] == '{':
            take('{'); result = {}
            while tokens[index] != '}':
                take('--'); field = take(); take(':'); result[field] = value()
            take('}'); return result
        name = token.rsplit('.', 1)[-1]
        if index < len(tokens) and tokens[index] == 'content':
            take('content'); return {name: value()}
        return name
    result = value()
    if index != len(tokens): raise ValueError('Trailing literal tokens')
    return result


def render_literal(kind: str, fields: dict) -> str:
    def render(field, value):
        if field == 'kind':
            enum = 'TermKind' if kind == 'Entity' else kind + 'Kind'
            return f'W.{enum}.{value}'
        if isinstance(value, bool): return str(value).lower()
        if field == 'amount': return f'(money of {value})'
        if isinstance(value, int): return str(value)
        if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): return '|'+value+'|'
        if isinstance(value, list):
            if kind != 'World' or field not in WORLD_LIST_TYPES:
                raise ValueError(f'Unsupported list field {kind}.{field}')
            return '[' + '; '.join(render_literal(WORLD_LIST_TYPES[field], item) for item in value) + ']'
        if isinstance(value, dict) and 'Known' in value:
            return f'W.FactValue.Known content (W.KnownValue.{value["Known"]})'
        if isinstance(value, dict) and 'Named' in value:
            return 'W.FactValue.Named content ('+render_literal('Entity', value['Named'])+')'
        if isinstance(value, dict):
            typ = 'Entity'
            if kind == 'World':
                family = field.split('_')[0]
                typ = {'financial':'FinancialFact','relationship':'RelationshipFact','employment':'EmploymentFact','status':'StatusFact'}.get(family, 'Entity')
            return render_literal(typ, value)
        raise ValueError(f'Unsupported {kind}.{field}: {value!r}')
    return 'W.'+kind+' { '+ ' '.join('-- '+field+': '+render(field, val) for field,val in fields.items())+' }'
