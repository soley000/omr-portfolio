{# pandas note les manques NaN ; en SQL, un manque doit etre NULL #}
{% macro nan_to_null(col) -%}
case when isnan({{ col }}) then null else {{ col }} end
{%- endmacro %}