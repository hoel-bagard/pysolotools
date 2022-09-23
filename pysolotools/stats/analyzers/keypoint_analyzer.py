import math
from typing import Any, List, Tuple

import numpy as np

from pysolotools.core import KeypointAnnotation, KeypointAnnotationDefinition
from pysolotools.core.models import DatasetAnnotations, Frame
from pysolotools.stats.analyzers.base import StatsAnalyzer

RIGHT_SHOULDER = "right_shoulder"
LEFT_SHOULDER = "left_shoulder"
RIGHT_HIP = "right_hip"
LEFT_HIP = "left_hip"


class KPPoseDict(StatsAnalyzer):
    def __init__(self, anno_def: DatasetAnnotations, **kwargs: Any):
        self.kp_lbl_map = _kp_label_dict(anno_def)
        self.label_idx_map = _reverse_map(self.kp_lbl_map)

    def analyze(
        self, frame: Frame = None, cat_ids: list = None, **kwargs: Any
    ) -> object:
        """
        Computes keypoints position stats.
        Args:
            frame (Frame): metadata of one frame
            cat_ids (list): list of category ids.
        Returns:
            keypoints_scaled_co-ordinates(dict): Dictionary of key points
            scaled co-ordinates
        """
        kp_pose_dict = {kp: {"x": [], "y": []} for kp in self.kp_lbl_map.keys()}
        annotations = _frame_keypoints(frame)
        for ann in annotations:
            for kp_ann in ann.values:
                if _is_torso_visible_or_labeled(kp_ann.keypoints, self.label_idx_map):
                    x_loc, y_loc = [], []
                    for kp in kp_ann.keypoints:
                        x_loc.append(kp.location[0])
                        y_loc.append(kp.location[1])
                    x_loc, y_loc = _translate_and_scale_xy(
                        np.array(x_loc), np.array(y_loc), self.label_idx_map
                    )

                    idx = 0
                    for xi, yi in zip(x_loc, y_loc):
                        if xi == 0 and yi == 0:
                            pass
                        elif xi > 2.5 or xi < -2.5 or yi > 2.5 or yi < -2.5:
                            pass
                        else:
                            kp_pose_dict[idx]["x"].append(xi)
                            kp_pose_dict[idx]["y"].append(yi)
                        idx += 1

        return {self.kp_lbl_map[key]: kp_pose_dict[key] for key in kp_pose_dict.keys()}

    def merge(self, results: dict, result: dict) -> object:
        """
        Merge computed stats values.
        Args:
            results (dict): aggregated results.
            result (dict):  result of one frame.
            Example: {'nose': {'x': [], 'y': []}

        Returns:
            aggregated stats values.

        """
        for k in result:
            for co_ord in result[k]:
                results[k][co_ord].extend(result[k][co_ord])

        return results


def _frame_keypoints(frame):
    keypoints = []

    for capture in frame.captures:
        keypoints.extend(
            filter(
                lambda k: isinstance(k, KeypointAnnotation),
                capture.annotations,
            )
        )
    return keypoints


def _is_torso_visible_or_labeled(kp: List, label_idx: dict) -> bool:
    torso = []
    for keypoint in filter(
        lambda k: k.index
        in [
            label_idx[RIGHT_SHOULDER],
            label_idx[LEFT_SHOULDER],
            label_idx[RIGHT_HIP],
            label_idx[LEFT_HIP],
        ],
        kp,
    ):
        torso.append(keypoint.state)

    if 0 in torso:
        return False
    return True


def _translate_and_scale_xy(x_arr: np.ndarray, y_arr: np.ndarray, label_idx: dict):

    left_hip, right_hip = (
        x_arr[label_idx[LEFT_HIP]],
        y_arr[label_idx[LEFT_HIP]],
    ), (x_arr[label_idx[RIGHT_HIP]], y_arr[label_idx[RIGHT_HIP]])
    left_shoulder, right_shoulder = (
        x_arr[label_idx[LEFT_SHOULDER]],
        y_arr[label_idx[LEFT_SHOULDER]],
    ), (x_arr[label_idx[RIGHT_SHOULDER]], y_arr[label_idx[RIGHT_SHOULDER]])

    # Translate all points according to mid_hip being at 0,0
    mid_hip = _calc_mid(right_hip, left_hip)
    x_arr = np.where(x_arr > 0.0, x_arr - mid_hip[0], 0.0)
    y_arr = np.where(y_arr > 0.0, y_arr - mid_hip[1], 0.0)

    # Calculate scale factor
    scale = (
        _calc_dist(left_shoulder, left_hip) + _calc_dist(right_shoulder, right_hip)
    ) / 2

    return x_arr / scale, y_arr / scale


def _calc_dist(p1: Tuple[Any, Any], p2: Tuple[Any, Any]) -> float:
    return math.sqrt(((p1[0] - p2[0]) ** 2) + ((p1[1] - p2[1]) ** 2))


def _calc_mid(p1: Tuple[Any, Any], p2: Tuple[Any, Any]):
    return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


def _kp_label_dict(dataset_annotation):
    kps = list(
        filter(
            lambda k: isinstance(k, KeypointAnnotationDefinition),
            dataset_annotation.annotationDefinitions,
        )
    )[0].template.keypoints
    return {kp.index: kp.label for kp in kps}


def _reverse_map(label_map):
    reverse_map = {}
    for k, v in label_map.items():
        reverse_map[v] = k

    return reverse_map


class AvgKPPerKPCat(StatsAnalyzer):
    """
    Computes average of per category of keypoints.
    """

    def __init__(self, anno_def: DatasetAnnotations, **kwargs: Any):
        self.kp_lbl_map = _kp_label_dict(anno_def)
        self.kp_anno_count = 0
        self.prev_anno_count = 0

    def analyze(
        self, frame: Frame = None, cat_ids: list = None, **kwargs: Any
    ) -> object:
        """
        Computes keypoints count.
        Args:
            frame (Frame): metadata of one frame
            cat_ids (list): list of category ids.
        Returns:
            keypoints_count(dict): Dictionary of key points count
        """
        kp_dict_count = {kp: 0 for kp in self.kp_lbl_map.keys()}
        annotations = _frame_keypoints(frame)
        self.prev_anno_count = self.kp_anno_count
        for ann in annotations:
            for kp_ann in ann.values:
                self.kp_anno_count += 1
                for kp in kp_ann.keypoints:
                    kp_dict_count[kp.index] += 1

        return {
            self.kp_lbl_map[key]: kp_dict_count[key] for key in kp_dict_count.keys()
        }

    def merge(self, results: dict, result: dict) -> object:
        """
        Merge computed stats values.
        Args:
            results (dict): aggregated results.
            result (dict):  result of one frame.

        Returns:
            aggregated stats dictionary.

        """
        for k in result:
            if self.prev_anno_count:
                results[k] *= self.prev_anno_count
            results[k] += result[k]
            results[k] /= self.kp_anno_count

        return results
