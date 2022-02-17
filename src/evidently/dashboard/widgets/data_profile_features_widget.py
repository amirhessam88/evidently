#!/usr/bin/env python
# coding: utf-8
import json
from typing import Optional, List

import logging

import pandas as pd
import numpy as np

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from evidently import ColumnMapping
from evidently.analyzers.data_profile_analyzer import DataProfileAnalyzer
from evidently.model.widget import BaseWidgetInfo, AdditionalGraphInfo
from evidently.dashboard.widgets.widget import Widget, GREY, RED, COLOR_DISCRETE_SEQUENCE


class DataProfileFeaturesWidget(Widget):
    period_prefix: str

    def analyzers(self):
        return [DataProfileAnalyzer]

    def calculate(self,
                  reference_data: pd.DataFrame,
                  current_data: Optional[pd.DataFrame],
                  column_mapping: ColumnMapping,
                  analyzers_results) -> Optional[BaseWidgetInfo]:
        self.period_prefix = ''
        is_current_data = current_data is not None
        data_profile_results = DataProfileAnalyzer.get_results(analyzers_results)
        columns = data_profile_results.columns.utility_columns
        target_column = columns.target
        if target_column:
            target_type = data_profile_results.reference_features_stats[target_column]['feature_type']
        else:
            target_type = None
        cat_feature_names = data_profile_results.columns.cat_feature_names
        date_column = columns.date
        self._transform_cat_features(reference_data, current_data, cat_feature_names, target_column, target_type)

        all_features = data_profile_results.columns.get_all_features_list(cat_before_num=True,
                                                                          include_datetime_feature=True)
        if date_column:
            all_features = [date_column] + all_features
        if target_column:
            all_features = [target_column] + all_features
        

        if is_current_data:
            metricsValuesHeaders = ["reference", "current"]
        else:
            metricsValuesHeaders = ['']

        widgets_list = []
        for feature_name in all_features:
            feature_type = data_profile_results.reference_features_stats[feature_name]['feature_type']
            fig_main_distr = self._plot_main_distr_figure(reference_data, current_data, feature_name, feature_type)
            parts = self.assemble_parts(target_column, date_column, feature_name, feature_type)
            additional_graphs = []
            if date_column and feature_type != 'datetime':
                freq = self._choose_agg_period(date_column, reference_data, current_data)
                reference_data[date_column + '_period'] = reference_data[date_column].dt.to_period(freq=freq)
                if current_data is not None:
                    current_data[date_column + '_period'] = current_data[date_column].dt.to_period(freq=freq)
                    feature_in_time_figure = self._plot_feature_in_time_2_df(reference_data, current_data, date_column,
                                                                             feature_name, feature_type)
                else:
                    feature_in_time_figure = self._plot_feature_in_time_1_df(reference_data, date_column, feature_name,
                                                                             feature_type)
                additional_graphs.append(
                    AdditionalGraphInfo(feature_name + "_in_time", {
                    "data": feature_in_time_figure['data'],
                    "layout": feature_in_time_figure['layout'],
                    }))

            if target_column and feature_name != target_column:
                if current_data is not None:
                    feature_and_target_figure = self._plot_feature_and_target_2_df(reference_data, current_data,
                                                                                   target_column, target_type,
                                                                                   feature_name, feature_type)
                else:
                    feature_and_target_figure = self._plot_feature_and_target_1_df(reference_data, target_column,
                                                                                   target_type, feature_name,
                                                                                   feature_type)
                additional_graphs.append(
                    AdditionalGraphInfo(feature_name + "_by_target", {
                    "data": feature_and_target_figure['data'],
                    "layout": feature_and_target_figure['layout'],
                    }))
            # fig_tmp = go.Figure()
            # fig_tmp.add_trace(go.Bar(x=[1, 2, 3, 4, 5], y=[0.1, 0.2, 0.3, 0.4, 0.5]))

            # fig_dict = fig_tmp.to_dict()
            # if feature_name=='date':
            #     logging.warning(self._metrics_for_table(feature_name, data_profile_results, is_current_data))

            wi = BaseWidgetInfo(
                type="expandable_list",
                title="",
                size=2,
                params={
                    "header": feature_name,
                    "description": feature_type,
                    "metricsValuesHeaders": metricsValuesHeaders,
                    "metrics": self._metrics_for_table(feature_name, data_profile_results, is_current_data),
                    "graph": {
                        "data": fig_main_distr['data'],
                        "layout": fig_main_distr['layout']
                    },
                    "details": {
                        "parts": parts,
                        "insights": []
                    }
                },
                additionalGraphs=additional_graphs
                
            )

            widgets_list.append(wi)

        return BaseWidgetInfo(
            title="",
            size=2,
            type="group",
            widgets=widgets_list
        )

    def _metrics_for_table(self, feature_name: str, data_profile_results, is_current_data: bool):
        metrics = []
        if is_current_data:
            vals = [list(x) for x in zip(data_profile_results.reference_features_stats[feature_name].values(), 
                                         data_profile_results.current_features_stats[feature_name].values())]
            for k, v in zip(data_profile_results.reference_features_stats[feature_name].keys(), vals):
                metrics.append({"label": k, "values": v})
        else:
            vals = [x for x in data_profile_results.reference_features_stats[feature_name].values()]
            for k, v in zip(data_profile_results.reference_features_stats[feature_name].keys(), vals):
                metrics.append({"label": k, "values": [v]})

        return metrics

    def _plot_main_distr_figure(self, reference_data: pd.DataFrame, current_data: pd.DataFrame,
                                feature_name: str, feature_type: str) -> dict:
        if feature_type == 'num':
            if current_data is None: 
                trace1 = go.Histogram(x=reference_data[feature_name], marker_color=RED)
                trace2 = go.Histogram(x=np.log10(reference_data.loc[reference_data[feature_name] > 0, feature_name]), 
                                    marker_color=RED, visible=False)
                data = [trace1, trace2]
                updatemenus=[ dict(
                            type="buttons",
                    direction="right",
                            x=1.0,
                            yanchor="top",
                            buttons=list([
                                dict(
                                    label='Linear Scale',
                                    method='update',
                                    args=[{'visible': [True, False]}]
                                ),
                                dict(
                                    label='Log Scale',
                                    method='update',
                                    args=[{'visible': [False, True]}]
                                )]))]

            else:
                trace1 = go.Histogram(x=reference_data[feature_name], marker_color=GREY)
                trace2 = go.Histogram(x=np.log10(reference_data.loc[reference_data[feature_name] > 0, feature_name]), 
                                    marker_color=GREY, visible=False)
                trace3 = go.Histogram(x=current_data[feature_name], marker_color=RED)
                trace4 = go.Histogram(x=np.log10(current_data.loc[current_data[feature_name] > 0, feature_name]), 
                                    marker_color=RED, visible=False)
                data = [trace1, trace2, trace3, trace4]
                
                updatemenus=[ dict(
                            type="buttons",
                    direction="right",
                            x=1.0,
                            yanchor="top",
                            buttons=list([
                                dict(
                                    label='Linear Scale',
                                    method='update',
                                    args=[{'visible': [True, False, True, False]}]
                                ),
                                dict(
                                    label='Log Scale',
                                    method='update',
                                    args=[{'visible': [False, True, False, True]}]
                                )]))]
            layout = dict(updatemenus=updatemenus)

            fig = go.Figure(data=data, layout=layout)

        elif feature_type == 'cat':
            fig = go.Figure()
            cats = list(reference_data[feature_name].value_counts().index.astype(str))
            cats = cats[::-1]
            if 'other' in cats:
                cats.remove('other')
                cats = ['other'] + cats
            if current_data is None: 
                fig.add_trace(go.Histogram(y=reference_data[feature_name], marker_color=RED))
            else:
                fig.add_trace(go.Histogram(y=reference_data[feature_name], marker_color=GREY, name='reference'))
                fig.add_trace(go.Histogram(y=current_data[feature_name], marker_color=RED, name='current'))
            fig.update_yaxes(categoryorder='array', categoryarray= cats)

        elif feature_type == 'datetime':
            freq = self._choose_agg_period(feature_name, reference_data, current_data)
            tmp_ref = reference_data[feature_name].dt.to_period(freq=freq)
            tmp_ref = tmp_ref.value_counts().reset_index()
            tmp_ref.columns = [feature_name, 'number_of_items']
            tmp_ref[feature_name] = tmp_ref[feature_name].dt.to_timestamp()
            fig = go.Figure()
            if current_data is None: 
                fig.add_trace(go.Scatter(x=tmp_ref.sort_values(feature_name)[feature_name], 
                                        y=tmp_ref.sort_values(feature_name)['number_of_items'],
                                        line=dict(color=RED, shape="spline")))
            else: 
                tmp_curr = reference_data[feature_name].dt.to_period(freq=freq)
                tmp_curr = tmp_curr.value_counts().reset_index()
                tmp_curr.columns = [feature_name, 'number_of_items']
                tmp_curr[feature_name] = tmp_curr[feature_name].dt.to_timestamp()
                fig.add_trace(go.Scatter(x=tmp_ref.sort_values(feature_name)[feature_name], 
                                        y=tmp_ref.sort_values(feature_name)['number_of_items'],
                                    line=dict(color=GREY, shape="spline"), name='reference'))
                fig.add_trace(go.Scatter(x=tmp_curr.sort_values(feature_name)[feature_name], 
                                        y=tmp_curr.sort_values(feature_name)['number_of_items'],
                                        line=dict(color=RED, shape="spline"), name='current'))

        fig.update_layout(xaxis_title=feature_name)
        fig_main_distr = json.loads(fig.to_json())
        return fig_main_distr

    def assemble_parts(self, target_column: Optional[str], date_column: Optional[str], feature_name: str, 
                       feature_type: str) -> List:
        parts = []
        if date_column and feature_type != 'datetime':
            parts.append({
                "title": feature_name + " in time",
                "id": feature_name + "_in_time"
            })
        if target_column and feature_name != target_column:
            parts.append({
                "title": feature_name + " by target",
                "id": feature_name + "_by_target"
            })
        return parts

    def _transform_df_to_time_mean_view(self, df: pd.DataFrame, date_column: str, feature_name: str):
        df = df.groupby(date_column + '_period')[feature_name].mean().reset_index()
        df[date_column] = df[date_column + '_period'].dt.to_timestamp()
        return df

    def _transform_df_to_time_count_view(self, df: pd.DataFrame, date_column: str, feature_name: str):
        df = df.groupby([date_column + '_period', feature_name]).size()
        df.name = 'num'
        df = df.reset_index()
        df[date_column] = df[date_column + '_period'].dt.to_timestamp()
        return df

    def _plot_feature_in_time_1_df(self, reference_data: pd.DataFrame, date_column: str, feature_name: str,
                                   feature_type: str) -> dict:
        tmp = reference_data[[date_column + '_period', feature_name]].copy()
        feature_in_time_figure = {}

        if feature_type == 'num':
            tmp = self._transform_df_to_time_mean_view(tmp, date_column, feature_name)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tmp.sort_values(date_column)[date_column],
                                     y=tmp.sort_values(date_column)[feature_name],
                                     line=dict(color=RED, shape="spline")))
            fig.update_layout(yaxis_title='Mean ' + feature_name + ' per ' + self.period_prefix)
            feature_in_time_figure = json.loads(fig.to_json())

        elif feature_type == 'cat':
            tmp = self._transform_df_to_time_count_view(tmp, date_column, feature_name)

            fig = go.Figure()
            for i, val in enumerate(tmp[feature_name].unique()):
                fig.add_trace(go.Bar(
                    x=tmp.loc[tmp[feature_name] == val, date_column],
                    y=tmp.loc[tmp[feature_name] == val, 'num'],
                    name=str(val),
                    marker_color=COLOR_DISCRETE_SEQUENCE[i]))
            fig.update_traces(marker_line_width=0.01)
            fig.update_layout(barmode='stack', bargap=0, yaxis_title='count category values per ' + self.period_prefix)

            feature_in_time_figure = json.loads(fig.to_json())

        return feature_in_time_figure

    def _plot_feature_in_time_2_df(self, reference_data: pd.DataFrame, current_data: pd.DataFrame,
                                   date_column: str, feature_name: str, feature_type: str) -> dict:
        tmp_ref = reference_data[[date_column + '_period', feature_name]].copy()
        tmp_curr = current_data[[date_column + '_period', feature_name]].copy()
        feature_in_time_figure = {}

        if feature_type == 'num':
            tmp_ref = self._transform_df_to_time_mean_view(tmp_ref, date_column, feature_name)
            tmp_curr = self._transform_df_to_time_mean_view(tmp_curr, date_column, feature_name)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tmp_ref.sort_values(date_column)[date_column],
                                     y=tmp_ref.sort_values(date_column)[feature_name],
                                     line=dict(color=GREY, shape="spline"), name='reference'))
            fig.add_trace(go.Scatter(x=tmp_curr.sort_values(date_column)[date_column],
                                     y=tmp_curr.sort_values(date_column)[feature_name],
                                     line=dict(color=RED, shape="spline"), name='current'))
            fig.update_layout(yaxis_title='Mean ' + feature_name + ' per ' + self.period_prefix)
            feature_in_time_figure = json.loads(fig.to_json())

        elif feature_type == 'cat':
            tmp_ref = self._transform_df_to_time_count_view(tmp_ref, date_column, feature_name)
            tmp_curr = self._transform_df_to_time_count_view(tmp_curr, date_column, feature_name)

            subplots_ratio = self._get_subplots_ratio(tmp_ref[date_column], tmp_curr[date_column])
            fig = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=("reference", "current"),
                                column_widths=subplots_ratio, horizontal_spacing=0.03)

            for i, val in enumerate(tmp_ref[feature_name].unique()):
                fig.add_trace(go.Bar(
                    x=tmp_ref.loc[tmp_ref[feature_name] == val, date_column],
                    y=tmp_ref.loc[tmp_ref[feature_name] == val, 'num'],
                    name=str(val),
                    marker_color=COLOR_DISCRETE_SEQUENCE[i], opacity=0.6, showlegend=False), 1, 1)
                fig.add_trace(go.Bar(
                    x=tmp_curr.loc[tmp_curr[feature_name] == val, date_column],
                    y=tmp_curr.loc[tmp_curr[feature_name] == val, 'num'],
                    name=str(val),
                    marker_color=COLOR_DISCRETE_SEQUENCE[i]), 1, 2)
            fig.update_traces(marker_line_width=0.01)
            fig.update_layout(
                barmode='stack', bargap=0, yaxis_title='count category values per ' + self.period_prefix
            )
            feature_in_time_figure = json.loads(fig.to_json())

        return feature_in_time_figure

    def _get_subplots_ratio(self, s1: pd.Series, s2: pd.Series):
        d1 = (s1.max() - s1.min()).days
        d2 = (s2.max() - s2.min()).days
        ratio = np.round(d1 / (d1 + d2), 3)
        return ratio, 1 - ratio

    def _transform_df_count_values(self, df: pd.DataFrame, target_column: str, feature_name: Optional[str]):
        df = df.groupby([target_column, feature_name]).size()
        df.name = 'count_objects'
        df = df.reset_index()
        return df

    def _plot_feature_and_target_1_df(self, reference_data: pd.DataFrame, target_column: str, target_type: str,
                                      feature_name: Optional[str], feature_type: str) -> dict:
        tmp = reference_data[[target_column, feature_name]].copy()
        if feature_type == 'cat':
            if target_type == 'num':
                fig = px.strip(
                    tmp.sample(2000, random_state=0), x=feature_name, y=target_column,
                    color_discrete_sequence=COLOR_DISCRETE_SEQUENCE
                )
                fig.update_traces(marker=dict(size=2))
            else:
                tmp = self._transform_df_count_values(tmp, target_column, feature_name)
                fig = go.Figure()
                for i, val in enumerate(tmp[target_column].unique()):
                    trace = go.Bar(
                        x=tmp.loc[tmp[target_column] == val, feature_name],
                        y=tmp.loc[tmp[target_column] == val, 'count_objects'],
                        marker_color=COLOR_DISCRETE_SEQUENCE[i], name=str(val)
                    )
                    fig.add_trace(trace)
                fig.update_layout(yaxis_title='count')
        else:
            if target_type == 'num':
                fig = go.Figure()
                trace = go.Scatter(x=tmp.sample(2000, random_state=0)[feature_name],
                                   y=tmp.sample(2000, random_state=0)[target_column], mode='markers', marker_color=RED)
                fig.add_trace(trace)

                fig.update_layout(yaxis_title=target_column, xaxis_title=feature_name)

            else:
                fig = px.strip(tmp.sample(2000, random_state=0), x=target_column, y=feature_name,
                               color_discrete_sequence=COLOR_DISCRETE_SEQUENCE)
                fig.update_traces(marker=dict(size=2))
        feature_and_target_figure = json.loads(fig.to_json())
        return feature_and_target_figure

    def _plot_feature_and_target_2_df(self, reference_data: pd.DataFrame, current_data: pd.DataFrame,
                                      target_column: str, target_type: str, feature_name: str,
                                      feature_type: str) -> dict:
        tmp_ref = reference_data[[target_column, feature_name]].copy()
        tmp_curr = current_data[[target_column, feature_name]].copy()
        tmp_ref['df'] = 'reference'
        tmp_curr['df'] = 'current'
        if feature_type == 'cat':
            if target_type == 'num':
                tmp = (tmp_ref.loc[:, [feature_name, target_column, 'df']].sample(2000)
                       .append(tmp_curr.loc[:, [feature_name, target_column, 'df']].sample(2000)))
                fig = px.strip(tmp, x=feature_name, y=target_column, color='df', color_discrete_sequence=[GREY, RED])
                fig.update_traces(marker=dict(size=2))
                fig.update_layout(legend_title_text='')
            else:
                tmp_ref = self._transform_df_count_values(tmp_ref, target_column, feature_name)
                tmp_curr = self._transform_df_count_values(tmp_curr, target_column, feature_name)
                fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                                    subplot_titles=['reference', 'current'])

                for i, val in enumerate(tmp_ref[target_column].unique()):
                    trace = go.Bar(x=tmp_ref.loc[tmp_ref[target_column] == val, feature_name],
                                   y=tmp_ref.loc[tmp_ref[target_column] == val, 'count_objects'],
                                   marker_color=COLOR_DISCRETE_SEQUENCE[i], opacity=0.6, showlegend=False)
                    fig.append_trace(trace, 1, 1)
                for i, val in enumerate(tmp_curr[target_column].unique()):
                    trace = go.Bar(x=tmp_curr.loc[tmp_curr[target_column] == val, feature_name],
                                   y=tmp_curr.loc[tmp_curr[target_column] == val, 'count_objects'],
                                   marker_color=COLOR_DISCRETE_SEQUENCE[i], name=str(val))
                    fig.append_trace(trace, 1, 2)
                fig.update_layout(yaxis_title='count')
        else:
            if target_type == 'num':
                fig = make_subplots(rows=1, cols=2, shared_yaxes=True)
                trace = go.Scatter(x=tmp_ref.sample(2000, random_state=0)[feature_name],
                                   y=tmp_ref.sample(2000, random_state=0)[target_column], mode='markers',
                                   marker_color=GREY, name='reference')
                fig.append_trace(trace, 1, 1)
                trace = go.Scatter(x=tmp_curr.sample(2000, random_state=0)[feature_name],
                                   y=tmp_curr.sample(2000, random_state=0)[target_column], mode='markers',
                                   marker_color=RED, name="current")
                fig.append_trace(trace, 1, 2)
                fig.update_layout(yaxis_title=target_column)
                fig.update_xaxes(title_text=feature_name, row=1, col=1)
                fig.update_xaxes(title_text=feature_name, row=1, col=2)

            else:
                tmp = (tmp_ref.loc[:, [feature_name, target_column, 'df']].sample(2000)
                       .append(tmp_curr.loc[:, [feature_name, target_column, 'df']].sample(2000)))
                fig = px.strip(tmp, x=target_column, y=feature_name, color='df', color_discrete_sequence=[GREY, RED])
                fig.update_traces(marker=dict(size=2))
                fig.update_layout(legend_title_text='')
        feature_and_target_figure = json.loads(fig.to_json())
        return feature_and_target_figure

    def _transform_cat_features(self, reference_data: pd.DataFrame, current_data: Optional[pd.DataFrame],
                                cat_feature_names: List[str], target_column: Optional[str],
                                target_type: Optional[str]):
        if target_column and target_type == 'cat':
            cat_feature_names = cat_feature_names + [target_column]
        for feature_name in cat_feature_names:
            if reference_data[feature_name].nunique() > 6:
                cats = reference_data[feature_name].value_counts()[:5].index.astype(str)
                reference_data[feature_name] = reference_data[feature_name].apply(lambda x: x if x in cats else 'other')
                if current_data is not None:
                    current_data[feature_name] = current_data[feature_name].apply(lambda x: x if x in cats else 'other')

    def _choose_agg_period(self, date_column: str, reference_data: pd.DataFrame,
                           current_data: Optional[pd.DataFrame]) -> str:
        OPTIMAL_POINTS = 150
        prefix_dict = {'A': 'year', 'Q': 'quarter', 'M': 'month', 'W': 'week', 'D': 'day', 'H': 'hour'}
        datetime_feature = reference_data[date_column]
        if current_data is not None:
            datetime_feature = datetime_feature.append(current_data[date_column])
        days = (datetime_feature.max() - datetime_feature.min()).days
        time_points = pd.Series(index=['A', 'Q', 'M', 'W', 'D', 'H'],
                                data=[abs(OPTIMAL_POINTS - days / 365), abs(OPTIMAL_POINTS - days / 90),
                                      abs(OPTIMAL_POINTS - days / 30), abs(OPTIMAL_POINTS - days / 7),
                                      abs(OPTIMAL_POINTS - days), abs(OPTIMAL_POINTS - days * 24)])
        self.period_prefix = prefix_dict[time_points.idxmin()]
        return str(time_points.idxmin())