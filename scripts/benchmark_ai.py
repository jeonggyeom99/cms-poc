"""Actual LLM single/multi comparison on one identical equipment snapshot.

uv run python scripts/benchmark_ai.py --dataset-id 1 --repeats 3 --cache-repeats 5
Uses the configured API key; output and validated traces default to .cache/.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai_analysis import AiAnalysisError, AiAnalysisService, OpenAIAnalysisGateway, OpenAISettings, load_project_environment
from app.agents.orchestrator import MultiAgentAnalysisGateway, analysis_configuration
from app.data_loader import load_datasets, load_history
from app.equipment_analysis import build_equipment_context, build_equipment_tool_executor
from app.main import DATA_DIR


class MeasuredSingleGateway(OpenAIAnalysisGateway):
    def __init__(self, settings):
        super().__init__(settings)
        self.completions = []

    async def analyze(self, context, execute=None):
        self.completions = []
        return await super().analyze(context, execute, observer=self.completions.append)


async def benchmark(args):
    load_project_environment(DATA_DIR.parent)
    settings = OpenAISettings.from_environment()
    dataset = load_datasets(DATA_DIR)[args.dataset_id]
    history = load_history(DATA_DIR)['items']
    report = {'dataset_id': args.dataset_id, 'model': settings.model, 'results': {}}
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in (('single', 'multi') if args.mode == 'both' else (args.mode,)):
        trace_dir = args.output / 'traces'
        gateway = (MeasuredSingleGateway(settings) if mode == 'single' else
                   MultiAgentAnalysisGateway(settings, trace_dir=trace_dir))
        service = AiAnalysisService(gateway, settings.model, cache_dir=args.output / f'{mode}-cache')
        runs, cached_runs = [], []
        for index in range(args.repeats):
            start = perf_counter()
            context = build_equipment_context(args.dataset_id, dataset, history, None, force=True)
            prefetch = perf_counter() - start
            context['agentConfiguration'] = analysis_configuration(mode, settings.model)
            execute = build_equipment_tool_executor(args.dataset_id, dataset, history, None, context)
            calls = []
            async def measured_execute(name, arguments):
                calls.append({'name': name, 'arguments': arguments})
                return await execute(name, arguments)
            try:
                result = await service.analyze(context, True, measured_execute, dataset_id=args.dataset_id)
                if mode == 'multi':
                    trace = json.loads(max(trace_dir.glob('*.json'), key=lambda p: p.stat().st_mtime_ns).read_text())
                    metrics = trace['metrics']
                    completions = metrics['completions']
                else:
                    completions = gateway.completions
                    metrics = {'agents': {}, 'fallback': False}
                runs.append({'seconds': perf_counter() - start, 'prefetch_seconds': prefetch,
                    'llm_calls': len(completions), 'evidence_lookups': len(calls),
                    'tool_calls': metrics.get('tool_calls',len(calls)),
                    'tokens': {key: sum(c[key] for c in completions) if all(c.get(key) is not None for c in completions) else None
                              for key in ('input_tokens','output_tokens','total_tokens')},
                    'request_id': trace['request_id'] if mode == 'multi' else None,
                    'agent_times': metrics['agents'], 'fallback': metrics['fallback'], 'status':'ready',
                    'synthesis_status': trace.get('synthesis', {}).get('status') if mode == 'multi' else None,
                    'validation_failures': metrics.get('validation_failures', []),
                    'phase_seconds': {'preparation': prefetch,
                        'specialist_parallel': metrics.get('specialist_parallel_seconds'),
                        'synthesis': metrics.get('agents', {}).get('synthesis', {}).get('seconds'),
                        'postprocessing_and_save': max(0, perf_counter() - start - prefetch - metrics['seconds']) if 'seconds' in metrics else None},
                    'result':result.model_dump(mode='json',by_alias=True)})
                print(json.dumps({'mode':mode,'run':index+1,**{k:v for k,v in runs[-1].items() if k!='result'}},ensure_ascii=False),flush=True)
            except AiAnalysisError as error:
                completions = gateway.completions if mode == 'single' else []
                if mode == 'multi' and trace_dir.exists():
                    paths = list(trace_dir.glob('*.json'))
                    if paths:
                        metrics = json.loads(max(paths, key=lambda p: p.stat().st_mtime_ns).read_text())['metrics']
                        completions = metrics['completions']
                runs.append({'status':'failed','code':error.code,'seconds':perf_counter()-start,
                    'prefetch_seconds':prefetch,'llm_calls':len(completions),'evidence_lookups':len(calls),
                    'tokens':{key:sum(c[key] for c in completions) if completions and all(c.get(key) is not None for c in completions) else None
                             for key in ('input_tokens','output_tokens','total_tokens')}})
                print(json.dumps({'mode':mode,'run':index+1,**runs[-1]}),flush=True)
                if error.code in {'provider_unavailable','rate_limit','not_configured','timeout'}:
                    break
        if any(item['status']=='ready' for item in runs):
            for _ in range(args.cache_repeats):
                start=perf_counter()
                context=build_equipment_context(args.dataset_id,dataset,history,None)
                context['agentConfiguration']=analysis_configuration(mode,settings.model)
                result=await service.analyze(context,dataset_id=args.dataset_id)
                cached_runs.append({'seconds':perf_counter()-start,'cached':result.cached})
        successful=[item['seconds'] for item in runs if item['status']=='ready']
        report['results'][mode]={'runs':runs,'cache_runs':cached_runs,
            'median_seconds':statistics.median(successful) if successful else None,
            'cache_median_seconds':statistics.median(item['seconds'] for item in cached_runs) if cached_runs else None}
        (args.output/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-id',default='1')
    parser.add_argument('--mode',choices=['both','single','multi'],default='both')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--cache-repeats',type=int,default=5)
    parser.add_argument('--output',type=Path,default=Path('.cache/multi-agent-benchmark'))
    options=parser.parse_args()
    if options.repeats<1 or options.cache_repeats<0:
        parser.error('repeats must be positive and cache-repeats non-negative')
    asyncio.run(benchmark(options))
