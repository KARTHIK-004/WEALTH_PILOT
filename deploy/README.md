# deploy/

`far_trans.zip` holds four unmodified files from the FAR-Trans dataset
(`customer_information.csv`, `asset_information.csv`, `transactions.csv`,
`close_prices.csv`). It exists only so a fresh deployment (Render) can fetch
them via `scripts/fetch_far_trans.py`; the canonical local copy remains
`datasets/raw/FAR-Trans/` (git-ignored, immutable).

FAR-Trans is licensed CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
Attribution: Javier Sanz-Cruzado, Nikolaos Droukas, Richard McCreadie.
*FAR-Trans: An Investment Dataset for Financial Asset Recommendation.*
IJCAI-2024 Workshop on Recommender Systems in Finance (Fin-RecSys), 2024.

SHA-256 of the zip: de900fb410765017da540b726a5cf53c32e28752b45062f5d0d5fc4e8442f9c8
