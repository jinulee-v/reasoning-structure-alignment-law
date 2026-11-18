"""Check normalized SARA inputs and all original gold tax expectations."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from .export_catala_tests import ROOT,generate,load_cases
from rsa_formalizer.stages.utils import toolchain_environment
from rsa_formalizer.stages.validation.verification import money_assertions_with_tolerance,_json_report


def check(output: Path | None = None):
    cases=list(load_cases())
    with tempfile.TemporaryDirectory(prefix='sara-canonical-check-') as tmp:
        project=Path(tmp)
        for source in (ROOT/'data/catala_gold/sara').glob('*.catala_en'):shutil.copy2(source,project/source.name)
        shutil.copy2(ROOT/'data/catala_gold/sara/clerk.toml',project/'clerk.toml')
        tests=generate().replace('result scope A.TotalTax','result scope A.TotalTaxFromWorld')
        (project/'SaraTaxCases.catala_en').write_text(money_assertions_with_tolerance(tests))
        env=toolchain_environment({});env['OPAMROOT']=str(ROOT/'.toolchain/opam')
        result=subprocess.run(['clerk','test','SaraTaxCases.catala_en','--json','--color=never'],cwd=project,env=env,capture_output=True,text=True,timeout=600)
        report=_json_report(result.stdout)
        rows=[row for file in (report or {}).get('test-results',[]) for row in file['tests']['scopes']]
        expected=set(name for name,_,_ in cases)
        if set(row['scope_name'] for row in rows)!=expected:
            raise RuntimeError('Missing native test results: '+(result.stdout+result.stderr)[-5000:])
        summary={'total':len(rows),'passed':sum(row['success'] for row in rows),'failed':[row['scope_name'] for row in rows if not row['success']],'money_tolerance':{'absolute':'1','exclusive':True},'cases':rows}
        if output:
            output.mkdir(parents=True,exist_ok=True)
            (output/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
            (output/'canonical_inputs.json').write_text(json.dumps({name:canonical for name,_,canonical in cases},indent=2)+'\n')
            (output/'clerk.log').write_text(result.stdout+result.stderr)
        if summary['failed']:raise RuntimeError(f"{summary['passed']}/{summary['total']} passed; failing scopes: {', '.join(summary['failed'])}")
        return summary


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'.port/sara_normalization/final');args=parser.parse_args()
    summary=check(args.output);print(f"Normalized gold Catala: {summary['passed']}/{summary['total']} passed")
if __name__=='__main__':main()
