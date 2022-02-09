from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Union

import numpy as np
import pandas

from evidently.pipeline.column_mapping import ColumnMapping


class DatasetUtilityColumns:
    def __init__(
            self,
            date: Optional[str],
            id_column: Optional[str],
            target: Optional[str],
            prediction: Optional[Union[str, Sequence[str]]],
    ) -> None:
        self.date = date
        self.id_column = id_column
        self.target = target
        self.prediction = prediction

    def as_dict(self) -> Dict[str, Union[Optional[str], Optional[Union[str, Sequence[str]]]]]:
        return {
            'date': self.date,
            'id': self.id_column,
            'target': self.target,
            'prediction': self.prediction,
        }


class DatasetColumns:
    def __init__(
            self,
            utility_columns: DatasetUtilityColumns,
            num_feature_names,
            cat_feature_names,
            datetime_feature_names,
            target_names: Optional[List[str]],
    ) -> None:
        self.utility_columns = utility_columns
        self.num_feature_names = num_feature_names
        self.cat_feature_names = cat_feature_names
        self.datetime_feature_names = datetime_feature_names
        self.target_names = target_names

    def as_dict(self) -> Dict[str, Union[Optional[List[str]], Dict]]:
        return {
            'utility_columns': self.utility_columns.as_dict(),
            'cat_feature_names': self.cat_feature_names,
            'num_feature_names': self.num_feature_names,
            'datetime_feature_names': self.datetime_feature_names,
            'target_names': self.target_names,
        }

    def get_all_features_list(self, cat_before_num: bool = True, include_time_columns: bool = False) -> List[str]:
        """List all features names"""
        if include_time_columns:
            add_time_columns = self.datetime_feature_names
        else:
            add_time_columns = []
        if cat_before_num:
            return self.cat_feature_names + self.num_feature_names + add_time_columns

        else:
            return self.num_feature_names + self.cat_feature_names + add_time_columns

    def get_features_len(self, include_time_columns: bool = False) -> int:
        """How mane feature do we have. It is useful for pagination in widgets."""
        if include_time_columns:
            len_time_columns = len(self.datetime_feature_names)
        else:
            len_time_columns = 0
        return len(self.num_feature_names) + len(self.cat_feature_names) + len_time_columns


def process_columns(dataset: pandas.DataFrame, column_mapping: ColumnMapping):
    date_column = column_mapping.datetime if column_mapping.datetime in dataset else None
    id_column = column_mapping.id
    target_column = column_mapping.target if column_mapping.target in dataset else None
    prediction_column = column_mapping.prediction
    num_feature_names = column_mapping.numerical_features
    cat_feature_names = column_mapping.categorical_features
    datetime_feature_names = column_mapping.datetime_features
    target_names = column_mapping.target_names
    utility_columns = [date_column, id_column, target_column]

    if isinstance(prediction_column, str):
        if prediction_column in dataset:
            prediction_column = prediction_column

        else:
            prediction_column = None

        utility_columns.append(prediction_column)

    elif prediction_column is None:
        pass

    else:
        prediction_column = dataset[prediction_column].columns.tolist()

        if prediction_column:
            utility_columns += prediction_column

    if num_feature_names is None:
        num_feature_names = list(set(dataset.select_dtypes([np.number]).columns) - set(utility_columns))

    else:
        num_feature_names = dataset[num_feature_names].select_dtypes([np.number]).columns.tolist()

    if datetime_feature_names is None:
        datetime_feature_names = list(set(dataset.select_dtypes(['datetime']).columns) - set(utility_columns))

    if cat_feature_names is None:
        cat_feature_names = list(set(dataset.select_dtypes(exclude=[np.number, 'datetime']).columns) - set(utility_columns))

    else:
        cat_feature_names = dataset[cat_feature_names].columns.tolist()

    return DatasetColumns(
        DatasetUtilityColumns(date_column, id_column, target_column, prediction_column),
        num_feature_names,
        cat_feature_names,
        datetime_feature_names,
        target_names,
    )
