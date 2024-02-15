import torch

from deepface import DeepFace
import numpy as np

def comfy_image_from_deepface_image(deepface_image):
    image_data = np.array(deepface_image).astype(np.float32)
    return torch.from_numpy(image_data)[None,]

def deepface_image_from_comfy_image(comfy_image):
    image_data = np.clip(255 * comfy_image.cpu().numpy(), 0, 255).astype(np.uint8)
    return image_data[:, :, ::-1]  # Convert RGB to BGR

def result_from_images_with_distances(images_with_distances):
    images_with_distances.sort(key=lambda row: row[1])
    images = [row[0] for row in images_with_distances]
    distances = [row[2] for row in images_with_distances]

    if len(images) > 0:
        return torch.stack(images, dim=0), distances
    else:
        # 64x64 black image, since it doesn't seem possible to output an empty batch of images that won't
        # break a connected PreviewImage or SaveImage node
        i = torch.full([1, 10, 10, 1], 0)
        return torch.cat((i, i, i), dim=-1), distances

class DeepfaceExtractFacesNode:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
            },
        }
 
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("face_images",)
 
    FUNCTION = "run"
 
    CATEGORY = "deepface"
 
    def run(self, images):
        target_face_size = (224, 224)

        output_images = []
        for image in images:
            image = deepface_image_from_comfy_image(image)

            detected_faces = DeepFace.extract_faces(
                image,
                detector_backend="retinaface",
                enforce_detection=False,
                target_size=target_face_size,
            )

            for detected_face in detected_faces:
                # print(detected_face["confidence"])
                face_image = comfy_image_from_deepface_image(detected_face["face"])
                output_images.append(face_image)

        if len(output_images) > 0:
            return (torch.cat(output_images, dim=0),)
        else:
            return ((),)

class DeepfaceVerifyNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "reference_images": ("IMAGE",),
                "threshold": ("FLOAT", {
                    "default": 0.3,
                    "display": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "step": 0.01,
                }),
                "detector_backend": ([
                     "opencv",
                     "ssd",
                     "dlib",
                     "mtcnn",
                     "retinaface",
                     "mediapipe",
                     "yolov8",
                     "yunet",
                     "fastmtcnn",
                ], {
                    "default": "retinaface",
                }),
                "model_name": ([
                     "VGG-Face",
                     "Facenet",
                     "Facenet512",
                     "OpenFace",
                     "DeepFace",
                     "DeepID",
                     "ArcFace",
                     "Dlib",
                     "SFace",
                ], {
                    "default": "Facenet512",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE", "STRING",)
    RETURN_NAMES = ("verified_images", "verified_image_distances", "rejected_images", "rejected_image_distances",)

    FUNCTION = "run"

    CATEGORY = "deepface"

    def run(self, images, reference_images, threshold, detector_backend, model_name):
        deepface_reference_images = []
        for reference_image in reference_images:
            deepface_reference_images.append(deepface_image_from_comfy_image(reference_image))

        rejected_images_with_distances = []
        verified_images_with_distances = []
        for image in images:
            print("Deepface verify")

            comparison_image = deepface_image_from_comfy_image(image)

            reference_image_counter = 1
            total_distance = 0
            for deepface_reference_image in deepface_reference_images:
                result = DeepFace.verify(
                    deepface_reference_image,
                    comparison_image,
                    detector_backend=detector_backend,
                    enforce_detection=False,
                    model_name=model_name
                )
                distance = result["distance"]
                print(f"  Distance to face image #{reference_image_counter}: {distance} ({result['verified']})")
                reference_image_counter += 1
                total_distance += distance

            average_distance = total_distance / len(deepface_reference_images)
            print(f"Average distance: {average_distance}")

            formatted_distance = "%.3f" % round(average_distance, 3)

            if average_distance < threshold:
                verified_images_with_distances.append((image, average_distance, formatted_distance))
            else:
                rejected_images_with_distances.append((image, average_distance, formatted_distance))

        return result_from_images_with_distances(verified_images_with_distances) + result_from_images_with_distances(rejected_images_with_distances)

NODE_CLASS_MAPPINGS = {
    "DeepfaceExtractFaces": DeepfaceExtractFacesNode,
    "DeepfaceVerify": DeepfaceVerifyNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DeepfaceExtractFaces": "Deepface Extract Faces",
    "DeepfaceVerify": "Deepface Verify",
}
