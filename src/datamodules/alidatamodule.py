#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import linecache
import random
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from PIL import Image
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader, Dataset, SubsetRandomSampler

from .build_dataset import build_dataset
from .utils import ALI_CATE_LEVEL_NAME, ALI_CATE_NAME, train_test_split


class ALIDataset(Dataset):
    def __init__(
        self,
        filename: Union[str, Path],
        use_image: bool = False,
        use_pv_pairs: bool = False,
        transforms: Optional[Callable] = None,
    ) -> None:
        self._filename = filename

        self._num_lines = 0
        with open(filename) as f:
            self._num_lines = sum(1 for _ in f)

        self._use_image = use_image
        self._use_pv_pairs = use_pv_pairs

        self.transforms = transforms

    def __getitem__(self, index: int):
        line = linecache.getline(str(self._filename), index + 1)
        raw = json.loads(line)

        res = {}
        res["raw"] = raw
        res["texts"] = []
        res["images"] = []

        def serialize_pv_pairs(pv_pairs):
            return " ".join([" ".join(p.split("#:#")) for p in pv_pairs.split("#;#")])

        imgs_dir = Path(self._filename).parent / "imgs"

        for suffix in ["left", "right"]:
            text = raw[f"title_{suffix}"]

            if self._use_pv_pairs:
                pv_pairs = serialize_pv_pairs(raw[f"pv_pairs_{suffix}"])
                text += " " + pv_pairs

            res["texts"].append(text)

            if self._use_image:
                img_path = imgs_dir / str(raw[f"id_{suffix}"])
                if img_path.exists():
                    image = Image.open(img_path).convert("RGB")
                else:
                    image = Image.fromarray(
                        255 * np.ones((256, 256, 3), dtype=np.uint8)
                    )

                image = self.transforms(image)

                res["images"].append(image)

        return res

    def __len__(self) -> int:
        return self._num_lines


class AliDataModule(LightningDataModule):
    def __init__(
        self,
        cate_name: Optional[ALI_CATE_NAME] = None,
        cate_level_name: Optional[ALI_CATE_LEVEL_NAME] = None,
        prod_num: int = 200,
        use_image: bool = False,
        use_pv_pairs: bool = False,
        batch_size: int = 32,
        num_workers: int = 4,
    ):
        super().__init__()
        self.save_hyperparameters()

        self.cate_name = cate_name
        self.cate_level_name = cate_level_name
        self.prod_num = prod_num

        self.use_image = use_image
        self.use_pv_pairs = use_pv_pairs

        self.batch_size = batch_size
        self.num_workers = num_workers

        self.version = f"{cate_name}_{cate_level_name}_{prod_num}_{use_image}_{use_pv_pairs}_{batch_size}"

    def prepare_data(self) -> None:
        column_names = [
            "id",
            "title",
            "pict_url",
            "cate_name",
            "cate_level_name",
            "pv_pairs",
            "cluster_id",
        ]

        cate_level_name = (
            ("_" + self.cate_level_name.replace("/", "_"))
            if self.cate_level_name
            else ""
        )
        cate_name = ("_" + self.cate_name.replace("/", "_")) if self.cate_name else ""

        self.data_path = Path(
            f"../data/ali/dataset{cate_level_name}{cate_name}_{self.prod_num}.json"
        )
        self.test_path = Path(
            f"../data/ali/testset{cate_level_name}{cate_name}_{self.prod_num}.json"
        )

        if not self.data_path.exists() or not self.test_path.exists():
            df = pd.read_csv(
                "../data/ali/same_product_train_sample_1wpid_USTC.txt",
                header=None,
                sep="@;@",
                names=column_names,
                engine="python",
            )

            if not self.data_path.exists():
                build_dataset(
                    df,
                    cate_name=self.cate_name,
                    cate_level_name=self.cate_level_name,
                    num=self.prod_num,
                    path=self.data_path,
                )

            if not self.test_path.exists():
                build_dataset(
                    df,
                    cate_name=self.cate_name,
                    cate_level_name=self.cate_level_name,
                    num=self.prod_num,
                    path=self.test_path,
                    size=5000,
                )

    def setup(self, stage: Optional[str]) -> None:
        if stage == "fit" or stage is None:
            dataset = ALIDataset(
                self.data_path,
                use_image=self.use_image,
                use_pv_pairs=self.use_pv_pairs,
                transforms=self.transforms,
            )
            self.data_train, self.data_valid = train_test_split(dataset, test_size=0.2)

        if stage == "test" or stage is None:
            self.data_test = ALIDataset(
                self.test_path,
                use_image=self.use_image,
                use_pv_pairs=self.use_pv_pairs,
                transforms=self.transforms,
            )

    def train_dataloader(
        self,
    ) -> Union[DataLoader, List[DataLoader], Dict[str, DataLoader]]:
        return DataLoader(
            dataset=self.data_train,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=True,
            pin_memory=False,
            collate_fn=self.collate_fn,
        )

    def val_dataloader(self) -> Union[DataLoader, List[DataLoader]]:
        return DataLoader(
            dataset=self.data_valid,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            pin_memory=False,
            collate_fn=self.collate_fn,
        )

    def test_dataloader(self) -> Union[DataLoader, List[DataLoader]]:
        return DataLoader(
            dataset=self.data_test,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            pin_memory=False,
            collate_fn=self.collate_fn,
        )