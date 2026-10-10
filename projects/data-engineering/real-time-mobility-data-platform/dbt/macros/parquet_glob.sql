{# Chemin de tous les fichiers Parquet d'un flux : <données>/parquet/<flux>/*/<flux>.parquet #}
{% macro parquet_glob(feed) -%}
{{ env_var('MOBILITYFLOW_DATA_DIR', 'C:/dev/mobilityflow-data') }}/parquet/{{ feed }}/*/*.parquet
{%- endmacro %}