"""Explicit, schema-checked tools reusing the historical retrieval implementations."""
import time
from pathlib import Path

from .config import ROOT, load_config, manifest_path
from .io_utils import read_jsonl
from .lexical_retrieval import LexicalIndex
from .product_evidence import evidence_for, inches, satisfies, validate_constraints

TOOL_ARGUMENTS = {
    "search_text": {"query", "top_k"}, "search_vector": {"query", "top_k"},
    "search_hybrid": {"query", "top_k"}, "search_image": {"image", "top_k"},
    "filter_products": {"product_ids", "constraints"}, "compare_products": {"product_ids"},
    "get_product": {"product_id"}}


class SearchTools:
    def __init__(self, catalog=None, config=None):
        self.config = config or load_config()
        self.catalog = catalog if catalog is not None else read_jsonl(manifest_path("mvp"))
        self.products = {p["product_id"]: p for p in self.catalog}
        if len(self.products) != len(self.catalog):
            raise ValueError("Duplicate catalog identity")
        self.lexical = LexicalIndex(self.catalog)
        self.encoder, self.vector = None, None
        self.reset()

    def reset(self, image_path=None):
        self.candidates, self.trace = {}, []
        self.image_path = Path(image_path) if image_path else None

    def warmup(self):
        if self.encoder is None:
            from .encoder_worker import EncoderWorker
            from .build_embeddings import catalog_embeddings
            from .exact_index import FaissFlatIndex
            self.encoder = EncoderWorker(self.config["encoder"])
            table, self.embedding_audit = catalog_embeddings(self.catalog, self.encoder)
            self.vector = FaissFlatIndex(table)
            self.encoder.encode_text(["chair"])

    def close(self):
        if self.encoder is not None:
            self.encoder.close()

    def _ids(self, ids):
        if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Expected unique product IDs, at most 100")
        if any(i not in self.candidates for i in ids):
            raise ValueError("Follow-up tool IDs must come from this request's retrieval")

    def invoke(self, name, arguments):
        started = time.perf_counter()
        entry = {"tool": name, "arguments": arguments, "success": False, "invalid_call": False}
        try:
            if len(self.trace) >= 8:
                raise ValueError("Tool-call budget exhausted")
            if name not in TOOL_ARGUMENTS or not isinstance(arguments, dict) or set(arguments) != TOOL_ARGUMENTS[name]:
                raise ValueError("Unknown tool or invalid argument schema")
            if name.startswith("search_"):
                k = arguments["top_k"]
                if type(k) is not int or not 1 <= k <= 100:
                    raise ValueError("top_k must be an integer from 1 to 100")
                if name == "search_image":
                    if arguments["image"] != "attached" or self.image_path is None or not self.image_path.is_file():
                        raise ValueError("search_image requires the attached image")
                    self.warmup()
                    hits = self.vector.search(self.encoder.encode_images([self.image_path])[0], k)
                else:
                    query = arguments["query"]
                    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
                        raise ValueError("query must be a nonempty string of at most 2000 characters")
                    if name == "search_text":
                        hits = self.lexical.search(query, k)
                    else:
                        self.warmup()
                        vector = self.vector.search(self.encoder.encode_text([query])[0], max(k, 50))
                        if name == "search_vector":
                            hits = vector[:k]
                        else:
                            from .hybrid_retrieval import reciprocal_rank_fusion
                            hits = reciprocal_rank_fusion({"lexical": self.lexical.search(query, max(k, 50)),
                                                          "vector": vector}, k=k)
                results = [evidence_for(self.products[h.product_id], h, i) for i, h in enumerate(hits, 1)]
                self.candidates.update({r["product_id"]: r for r in results})
                result = {"products": results}
            elif name == "get_product":
                self._ids([arguments["product_id"]])
                result = self.candidates[arguments["product_id"]]
            else:
                ids = arguments["product_ids"]
                self._ids(ids)
                if name == "filter_products":
                    constraints = validate_constraints(arguments["constraints"])
                    products = [self.candidates[i] for i in ids if satisfies(self.candidates[i], constraints)]
                    result = {"products": products, "input_count": len(ids), "excluded_count": len(ids) - len(products)}
                else:
                    rows = [{"product_id": i, "fields": self.candidates[i]["fields"],
                             "dimension_sources": self.candidates[i]["dimension_sources"]} for i in ids]
                    widths = sorted((inches(r["fields"]["width"]), r["product_id"]) for r in rows if "width" in r["fields"])
                    narrowest = widths[0][1] if widths else None
                    result = {"products": rows, "width_count": len(widths), "missing_width_count": len(rows) - len(widths),
                              "narrowest_product_id": narrowest,
                              "narrowest_width": self.candidates[narrowest]["fields"]["width"] if narrowest else None}
            entry.update(success=True, result=result)
        except ValueError as error:
            entry.update(error=str(error), invalid_call=True)
        except Exception as error:
            entry["error"] = type(error).__name__ + ": tool execution failed"
        entry["latency_ms"] = (time.perf_counter() - started) * 1000
        self.trace.append(entry)
        return entry
