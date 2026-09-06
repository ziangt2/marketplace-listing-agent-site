# Public ABO data and attribution

Source: [Amazon Berkeley Objects research dataset](https://amazon-berkeley-objects.s3.amazonaws.com/index.html).
Data, images and metadata are © Amazon.com, available under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
This project selects and normalizes English metadata and uses the publisher's
downscaled images. It is not proprietary Amazon production data or an endorsement.

Credit for dataset construction: Matthieu Guillaumin, Thomas Dideriksen, Kenan
Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine
Collins, Shubham Goel, and Jitendra Malik. Research reference:
[Collins et al., ABO: Dataset and Benchmarks for Real-World 3D Object Understanding, CVPR 2022](https://amazon-berkeley-objects.s3.amazonaws.com/static_html/ABO_CVPR2022.pdf).

The downloader reads the 16 `listings/metadata/listings_*.json.gz` files and
`images/metadata/images.csv.gz`. It requests only selected
`images/small/<path>` files (maximum axis 256 pixels). It does not request any
original-image, spin, 3D-model, or complete image archive.

`raw/`, `cache/`, and `processed/` are ignored by Git. Manifests preserve
original `item_id`/image IDs, the selected listing domain, English title/type,
material/color/style/brand/pattern/finish, dimensions when present, original
image URLs, relative paths, byte checksums, decoded-pixel checksums, and shape.
Model numbers are retained solely for leakage checks, never query construction.
Compact metadata and benchmark definitions are included for reproducibility.

Subset rule: require an English title, product type and usable image metadata;
choose one listing per item (prefer amazon.com); sort multiple-view products
first, then SHA256 of `[seed, item_id]`; examine candidates in that order until
the requested number of usable, distinct indexed images is reached. Main image
is preferred, followed by the listed alternate order, with at most two initial
image downloads per candidate. Missing/invalid images and duplicate indexed
image contents are counted. Transient network failures stop the run after
retries, rather than silently changing the population.

Image queries must be distinct from every indexed image by ID, file SHA256 and
decoded RGB-pixel SHA256. For single-product ground truth, the query image must
also be unique to one product within the selected catalog. Shared alternate
views are excluded by `build_image_queries`; they can remain in the source
catalog manifest but never enter image metrics. Per-product target identity is
retained; variants and near-duplicates can still make this task difficult.

`catalog_<profile>.summary.json` records selection and source-metadata checksums.
An existing manifest is restored by exact URL and checksum and never silently
reselected. `queries_<profile>_v2.jsonl` contains complete evaluated queries and
relevance sets. The first query-definition attempt predated shared-view exclusion
and failed before publishing results because of an OpenMP conflict; v2 names
make that ground-truth change explicit.
