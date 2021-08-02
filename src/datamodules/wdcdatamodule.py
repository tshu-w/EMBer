#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Union

import numpy as np
import pandas as pd
from PIL import Image
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader, Dataset


class WDCDataset(Dataset):
    def __init__(
        self,
        dataframe: pd.DataFrame,
        imgs_dir: Path,
        use_image: bool = False,
        transforms: Optional[Callable] = None,
    ) -> None:
        self._dataframe = dataframe
        self._imgs_dir = imgs_dir
        self._len = len(dataframe)

        self._use_image = use_image
        self.transforms = transforms

    def __getitem__(self, index):
        raw = self._dataframe.iloc[index].to_dict()

        res = {}
        res["raw"] = raw
        res["texts"] = []
        res["images"] = []

        for suffix in ["left", "right"]:
            text = raw[f"title_{suffix}"]

            res["texts"].append(text)

            if self._use_image:
                id = raw[f"id_{suffix}"]
                img_paths = sorted(self._imgs_dir.glob(f"{id}_*"))

                if img_paths:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        image = Image.open(img_paths[0]).convert("RGB")

                else:
                    image = Image.fromarray(
                        255 * np.ones((256, 256, 3), dtype=np.uint8)
                    )

                image = self.transforms(image)
                res["images"].append(image)

        return res

    def __len__(self):
        return self._len


class WDCDataModule(LightningDataModule):
    def __init__(
        self,
        cate: Literal["all", "cameras", "computers", "shoes", "watches"] = "all",
        training_size: Literal["small", "medium", "large", "xlarge"] = "medium",
        use_image: bool = True,
        batch_size: int = 32,
        num_workers: int = 4,
    ):
        super().__init__()
        self.save_hyperparameters()

        self.cate = cate
        self.training_size = training_size
        self.use_image = use_image

        self.batch_size = batch_size
        self.num_workers = num_workers

        self.version = f"{cate}_{training_size}_{use_image}_{batch_size}"

    def prepare_data(self) -> None:
        return super().prepare_data()

    def setup(self, stage: Optional[str]) -> None:
        data_dir = Path("../data/wdc/norm/")
        imgs_dir = Path("../data/wdc/imgs")

        if stage == "fit" or stage is None:
            training_path = (
                data_dir
                / "training-sets"
                / f"{self.cate}_train"
                / f"{self.cate}_train_{self.training_size}.json.gz"
            )
            training_df = pd.read_json(training_path, lines=True)

            validation_set_path = (
                data_dir
                / "validation-sets"
                / f"{self.cate}_valid"
                / f"{self.cate}_valid_{self.training_size}.csv"
            )
            validation_pair_id = pd.read_csv(validation_set_path)["pair_id"]

            self.data_train = WDCDataset(
                dataframe=training_df[~training_df["pair_id"].isin(validation_pair_id)],
                imgs_dir=imgs_dir,
                use_image=self.use_image,
                transforms=self.transforms,
            )
            self.data_valid = WDCDataset(
                dataframe=training_df[training_df["pair_id"].isin(validation_pair_id)],
                imgs_dir=imgs_dir,
                use_image=self.use_image,
                transforms=self.transforms,
            )

        if stage == "test" or stage is None:
            test_set_path = data_dir / "gold-standards" / f"{self.cate}_gs.json.gz"
            self.data_test = WDCDataset(
                dataframe=pd.read_json(test_set_path, lines=True),
                imgs_dir=imgs_dir,
                use_image=self.use_image,
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