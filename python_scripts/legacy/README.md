# Preserved analysis entry points

`analyze_benchmark.py CONFIG --run RUN` and
`execute_notebook.py CONFIG --run RUN --output NEW.ipynb` preserve the pre-migration
consumer behavior and route to `analysis.legacy`. CONFIG is a full benchmark YAML,
for example `config/legacy/smoke.yaml.example`. The notebook defaults to the
preserved template in notebook/legacy/. Use the active search_decimation environment.

Simulation, replay, preparation and dependency-build CLIs stay shared in the parent
directory. Legacy decoder selection remains configuration-driven; no decoder
implementation or immutable scientific artifact was moved or relabeled.
