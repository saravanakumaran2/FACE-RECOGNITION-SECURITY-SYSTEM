import os
from datetime import datetime
import cv2
import face_recognition as fr
import smtplib
from email.message import EmailMessage
import pyttsx3
import pywhatkit as pwk
from pymongo import MongoClient

# Initialize datetime object to use current time
myobj = datetime.now()

# Load the Haar Cascade Classifier for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Initialize video capture from the webcam
video_capture = cv2.VideoCapture(0)

# Function to load known faces from MongoDB
def load_known_faces_from_mongo():
    client = MongoClient('mongodb://localhost:27017/')
    db_name = 'security_db'
    mongo_db = client[db_name]
    profiles_collection = mongo_db['profiles']

    known_faces = {}

    for profile in profiles_collection.find():
        profile_name = profile['profile_name']
        for image_info in profile['images']:
            image_filename = image_info['filename']
            image_path = os.path.join("uploads", profile_name, image_filename)
            if os.path.exists(image_path):
                known_image = fr.load_image_file(image_path)
                known_face_encoding = fr.face_encodings(known_image)
                if known_face_encoding:
                    known_faces[profile_name] = known_face_encoding[0]
    
    return known_faces

known_faces = load_known_faces_from_mongo()

# Counter for saved frames
i = 0

while True:
    # Capture frame from the webcam
    ret, frame = video_capture.read()
    if not ret:
        print("Failed to capture image from camera.")
        break

    # Convert the frame to grayscale for face detection
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces in the frame
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    for (x, y, w, h) in faces:
        face_image = gray_frame[y:y + h, x:x + w]

        # Perform face recognition
        face_encodings = fr.face_encodings(frame, [(y, x + w, y + h, x)])

        if len(face_encodings) > 0:
            face_encoding = face_encodings[0]
            name = "Unknown"
            for profile_name, known_face_encoding in known_faces.items():
                matches = fr.compare_faces([known_face_encoding], face_encoding)
                if matches[0]:
                    name = profile_name
                    break

            # If face is unknown, save the frame, send email and WhatsApp message
            if name == "Unknown":
                image_path = f'Frame{i}.jpg'
                cv2.imwrite(image_path, frame)
                converter = pyttsx3.init()
                converter.setProperty('rate', 125)
                converter.setProperty('volume', 1.0)
                converter.say("Unknown person detected")
                converter.runAndWait()

                # Send WhatsApp image with minimal delay
                pwk.sendwhats_image("+14169373216", image_path, "Unknown person detected!", wait_time=15, tab_close=True)

                # Prepare and send email notification
                msg = EmailMessage()
                msg['Subject'] = 'Unknown Person Detected'
                msg['From'] = 'devopsgroup22024@gmail.com'
                msg['To'] = 'devopsgroup22024@gmail.com'
                msg.set_content('Unknown person detected.')

                with open(image_path, 'rb') as f:
                    file_data = f.read()
                    file_name = f.name
                    msg.add_attachment(file_data, maintype="application", subtype="jpg", filename=file_name)

                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login('devopsgroup22024@gmail.com', 'nuya lwzs hkml mpdd')
                        server.send_message(msg)
                    print('Mail sent')
                except Exception as e:
                    print(f'Failed to send email: {e}')

            # If face is known, greet and send email notification
            elif name in known_faces:
                converter = pyttsx3.init()
                converter.setProperty('rate', 125)
                converter.setProperty('volume', 1.0)
                converter.say("Welcome home")
                converter.runAndWait()

                # Prepare and send email notification
                msg = EmailMessage()
                msg['Subject'] = 'Home'
                msg['From'] = 'devopsgroup22024@gmail.com'
                msg['To'] = 'devopsgroup22024@gmail.com'
                msg.set_content(f'{name} at home.')

                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login('devopsgroup22024@gmail.com', 'nuya lwzs hkml mpdd')
                        server.send_message(msg)
                    print('Mail sent')
                except Exception as e:
                    print(f'Failed to send email: {e}')


        # Display the frame with face recognition annotations
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    # Show the frame with annotations
    cv2.imshow('Webcam Face Recognition', frame)

    # Exit loop if 'q' key is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release video capture and close all windows
video_capture.release()
cv2.destroyAllWindows()
