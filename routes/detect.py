import io
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from services.solution_service import SolutionService
from services.yolo_service import YOLOService
from services.model_service import ModelService

router = APIRouter()

yolo_service = YOLOService()
solution_service = SolutionService()

@router.post("/")
async def detect(plant_type: str = Form(...), image: UploadFile = File(...)):
    """
    Detect objects and return an image with bounding boxes.
    """
    # Validate model with plant type
    validation = ModelService.validate_plant_type(plant_type)

    if(validation != None):
        raise HTTPException(400, validation)

    # Validate model
    try:
        model = yolo_service.load_model(plant_type)
    except ValueError as e:
        error = {
            "status": "error",
            "message": str(e),
        }
        raise HTTPException(400, error)
    
    image_data = await image.read()

    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        error = {
            "status": "error",
            "message": "Failed to decode image. The image may be corrupted or invalid."
        }

        raise HTTPException(400, error)

    # Run the predictions
    predictions = yolo_service.predict(model, img)

    # Annotate image
    annotated_img = img.copy()
    for result in predictions:
        # Extract bounding box coordinates
        x1, y1, x2, y2 = map(int, result['box'])
        
        solution_data = solution_service.get_solution_data(plant_type, result['class_name'])

        # Prepare label with class name and confidence
        label = f"{solution_data['disease_label']} {result['confidence']:.2f}"
        
        # Draw bounding box and label
        cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated_img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Encode and return the annotated image
    _, encoded_img = cv2.imencode(".jpg", annotated_img)
    return StreamingResponse(io.BytesIO(encoded_img.tobytes()), media_type="image/jpeg")
