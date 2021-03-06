"""
Copyright 2017-2018 Fizyr (https://fizyr.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from pycocotools.cocoeval import COCOeval

import keras
import numpy as np
import json

import progressbar
assert(callable(progressbar.progressbar)), "Using wrong progressbar module, install 'progressbar2' instead."


def evaluate_coco(generator, model, threshold=0.05, cat_ids=None):
    """ Use the pycocotools to evaluate a COCO model on a dataset.

    Args
        generator : The generator for generating the evaluation data.
        model     : The model to evaluate.
        threshold : The score threshold to use.
        cat_ids    : The category indices to evaluate (if None, the default nº of categories is evaluated)
    """
    # start collecting results
    results = []
    image_ids = []
    for index in progressbar.progressbar(range(generator.size()), prefix='COCO evaluation: '):
        image = generator.load_image(index)
        image = generator.preprocess_image(image)
        image, scale = generator.resize_image(image)

        if keras.backend.image_data_format() == 'channels_first':
            image = image.transpose((2, 0, 1))

        # run network
        boxes, scores, labels = model.predict_on_batch(np.expand_dims(image, axis=0))

        # correct boxes for image scale
        boxes /= scale

        # change to (x, y, w, h) (MS COCO standard)
        boxes[:, :, 2] -= boxes[:, :, 0]
        boxes[:, :, 3] -= boxes[:, :, 1]

        # compute predicted labels and scores
        for box, score, label in zip(boxes[0], scores[0], labels[0]):
            # scores are sorted, so we can break
            if score < threshold:
                break

            # print("label: {0}, 'cat_ids is not None':{1}".format(label, cat_ids is not None))
            if "aicity" in generator.data_dir:
                if (label == 2) and (cat_ids is not None):  # apply quick (hardcoded) fix ONLY for car class
                    # This is necessary because the loaded module detected all 81 classes from Coco
                    # A better solution would be to 'fix' the mapping from retina labels to coco as needed
                    # This would depen on the number of classes of the subset and which
                    # This quick fix works because: generator.label_to_coco_label(0)=3 (desired coco label)
                    image_result = {
                        'image_id': generator.image_ids[index],
                        'category_id': generator.label_to_coco_label(0),
                        'score': float(score),
                        'bbox': box.tolist(),
                    }
                    # Super-hardcoded(specially below)
                elif (label != 2) and (cat_ids is not None):  # we do not want to evaluate other classes
                    continue  # go to next bbox

            else:  # ALL detected classes are evaluated (default behaviour)
                # append detection for each positively labeled class
                # print("label: {0}".format(label))
                image_result = {
                    'image_id': generator.image_ids[index],
                    'category_id': generator.label_to_coco_label(label),
                    'score': float(score),
                    'bbox': box.tolist(),
                }

            # append detection to results
            results.append(image_result)

        # append image to list of processed images
        image_ids.append(generator.image_ids[index])

    if not len(results):
        return

    # write output
    json.dump(results, open('{}_bbox_results.json'.format(generator.set_name), 'w'), indent=4)
    json.dump(image_ids, open('{}_processed_image_ids.json'.format(generator.set_name), 'w'), indent=4)

    # load results in COCO evaluation tool
    coco_true = generator.coco
    coco_pred = coco_true.loadRes('{}_bbox_results.json'.format(generator.set_name))

    # run COCO evaluation
    coco_eval = COCOeval(coco_true, coco_pred, 'bbox')
    coco_eval.params.imgIds = image_ids
    # So we can only assess a set of classes instead of all
    if cat_ids is not None:
        coco_eval.params.catIds = cat_ids
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()
    return coco_eval.stats
