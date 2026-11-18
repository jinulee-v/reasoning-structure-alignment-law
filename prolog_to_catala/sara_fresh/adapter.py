"""Legacy factual JSON -> validated canonical view -> list-based Catala input projection.

The canonical view is derived, never another independently editable fact channel.
This adapter does not derive statutory conclusions or infer economic identity.
"""
from __future__ import annotations
from copy import deepcopy
from .normalization import normalize_world


def catala_inputs(inputs: dict) -> dict:
    """Accept factual World/Entity/TaxPeriod JSON and normalize legacy aliases."""
    if set(inputs) != {'world','taxpayer','period'}:
        raise ValueError('Expected exactly world, taxpayer, and period')
    result=deepcopy(inputs)
    result['world']=normalize_world(result['world'])['world']
    return result


def main():
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--canonical',action='store_true',help='write derived canonical facts with legacy provenance')
    args=parser.parse_args();inputs=json.loads(args.input.read_text())
    result=normalize_world(inputs['world']) if args.canonical else catala_inputs(inputs)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
