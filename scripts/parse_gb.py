from Bio import SeqIO
from collections import OrderedDict, Counter
import pandas as pd
from datetime import datetime
import re
import numpy as np


def fix_date(x):
    try:
        d = datetime.strptime(x, "%d-%b-%Y")
        fixed = datetime.strftime(d, "%Y-%m-%d")
    except Exception:
        fixed = x
        pass
    return fixed


sars = "Severe acute respiratory syndrome coronavirus 2 (isolate )?"
gen = ", complete genome"
min_length = snakemake.params.get("min_length", 25000)

ord_list = []
strain = []
with open(snakemake.output.fasta, "w") as fasta_handle:
    for seq_record in SeqIO.parse(snakemake.input[0], "genbank"):
        if len(seq_record.seq) > min_length:
            q = seq_record.features[0]
            refs = seq_record.annotations["references"][0]
            ids = {
                "accession": re.sub("\.\d$", "", seq_record.id),
                "description": seq_record.description,
                "length": len(seq_record.seq),
            }
            qualifiers = {k: v[0] for k, v in q.qualifiers.items()}
            # Skip record if collection_date or country is missing
            if "country" not in qualifiers:
                continue
            if "collection_date" not in qualifiers:
                continue
            if "strain" not in qualifiers:
                qualifiers.update({"strain": None})
            if not qualifiers["strain"]:
                if "isolate" in qualifiers:
                    qualifiers["strain"] = qualifiers["isolate"]
                else:
                    qualifiers["strain"] = ids["accession"]
            # Checking if we have unique strain ids
            if qualifiers["strain"] not in strain:
                strain.append(qualifiers["strain"])
            else:
                qualifiers["strain"] = qualifiers["strain"] + "/" + ids["accession"]
                strain.append(qualifiers["strain"])
            ids.update(qualifiers)
            # Replace space with backslashes to fix fasta headers
            ids["strain"] = ids["strain"].replace(" ", "/")
            # Add references
            ids.update(
                {"author": refs.authors, "journal": refs.journal, "title": refs.title}
            )
            ord_list.append(ids)
            fasta_handle.write(">{}\n{}\n".format(ids["strain"], seq_record.seq))


if "metadata" in snakemake.output.keys():

    # Parsing metadata
    df = pd.DataFrame(ord_list, columns=ord_list[0].keys()).set_index(
        "strain", drop=False
    )
    df_renamed = df.rename(columns={"organism": "virus", "collection_date": "date"})
    df_renamed["date"] = df_renamed["date"].apply(lambda x: fix_date(x))
    new = df_renamed["country"].str.split(": ?", expand=True)
    df_renamed["division"] = new[1]
    df_renamed["country"] = new[0]

    # Replace missing values in author col with 'unknown'
    df_renamed.replace("", np.nan, inplace=True)
    df_renamed["author"] = df_renamed.author.fillna("unknown")

    # Writing metadata to file
    df_renamed.to_csv(snakemake.output.metadata, sep="\t", index=False)
