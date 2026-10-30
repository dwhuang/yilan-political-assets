# 宜蘭縣政治人物不動產地圖 — build pipeline
# Everyday rebuilds use the committed NLSC cache (inputs/geo/nlsc_cache.jsonl)
# and make NO network calls. `make site` regenerates everything.

.PHONY: site data xlsx sections map probes sample clean

site: data sections map probes   ## full rebuild from the committed cache (no API calls)

data:       ## inputs/ -> output/yilan.json  (parse filings, attach value estimates)
	python3 scripts/extract.py

sections:   ## NLSC cache + output/yilan.json -> output/{section_geo,map_data,placement}.json
	python3 scripts/build_sections.py

map:        ## output/map_data.json + output/poi.json -> docs/index.html (the published map)
	python3 scripts/build_map_html.py

probes:     ## NLSC cache -> docs/probes.html (sampling debug view)
	python3 scripts/build_probes_html.py

xlsx:       ## output/yilan.json -> output/宜蘭縣政治人物不動產申報.xlsx
	python3 scripts/build_xlsx.py

# --- one-time, SLOW: (re)build the NLSC section cache by sampling the public API.
# Hours of polite, rate-limited calls. Only needed if you delete/rebuild the cache.
sample:     ## reverse-sample + refine the NLSC section API into inputs/geo/nlsc_cache.jsonl
	python3 scripts/geocode_sections.py plain
	python3 scripts/geocode_sections.py mountain
	python3 scripts/geocode_sections.py gaps
	python3 scripts/geocode_sections.py gaps2
	python3 scripts/refine_boundaries.py 25 46000

clean:      ## remove generated data/site (keeps inputs/ and the cache)
	rm -f output/*.json output/*.xlsx docs/index.html docs/probes.html
