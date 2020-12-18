from scipy.spatial import distance
from imutils import face_utils
import numpy as np
import pygame #For playing sound
import time
import dlib
import cv2

def drow():
    #Initialize Pygame and load music
    pygame.mixer.init()
    pygame.mixer.music.load('audio/alert.wav')

    #Minimum threshold of eye aspect ratio below which alarm is triggerd
    EYE_ASPECT_RATIO_THRESHOLD = 0.3

    #Minimum consecutive frames for which eye ratio is below threshold for alarm to be triggered
    EYE_ASPECT_RATIO_CONSEC_FRAMES = 50

    #COunts no. of consecutuve frames below threshold value
    COUNTER = 0

    #Load face cascade which will be used to draw a rectangle around detected faces.
    face_cascade = cv2.CascadeClassifier("haarcascades/haarcascade_frontalface_default.xml")

    #This function calculates and return eye aspect ratio
    def eye_aspect_ratio(eye):
        A = distance.euclidean(eye[1], eye[5])
        B = distance.euclidean(eye[2], eye[4])
        C = distance.euclidean(eye[0], eye[3])

        ear = (A+B) / (2*C)
        return ear

    #Load face detector and predictor, uses dlib shape predictor file
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor('shape_predictor_68_face_landmarks.dat')

    #Extract indexes of facial landmarks for the left and right eye
    (lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS['left_eye']
    (rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS['right_eye']

    #Start webcam video capture
    video_capture = cv2.VideoCapture(0)

    #Give some time for camera to initialize(not required)
    time.sleep(2)

    while(True):
        #Read each frame and flip it, and convert to grayscale
        ret, frame = video_capture.read()
        frame = cv2.flip(frame,1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        #Detect facial points through detector function
        faces = detector(gray, 0)

        #Detect faces through haarcascade_frontalface_default.xml
        face_rectangle = face_cascade.detectMultiScale(gray, 1.3, 5)

        #Draw rectangle around each face detected
        for (x,y,w,h) in face_rectangle:
            cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)

        #Detect facial points
        for face in faces:

            shape = predictor(gray, face)
            shape = face_utils.shape_to_np(shape)

            #Get array of coordinates of leftEye and rightEye
            leftEye = shape[lStart:lEnd]
            rightEye = shape[rStart:rEnd]

            #Calculate aspect ratio of both eyes
            leftEyeAspectRatio = eye_aspect_ratio(leftEye)
            rightEyeAspectRatio = eye_aspect_ratio(rightEye)

            eyeAspectRatio = (leftEyeAspectRatio + rightEyeAspectRatio) / 2

            #Use hull to remove convex contour discrepencies and draw eye shape around eyes
            leftEyeHull = cv2.convexHull(leftEye)
            rightEyeHull = cv2.convexHull(rightEye)
            cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)

            #Detect if eye aspect ratio is less than threshold
            if(eyeAspectRatio < EYE_ASPECT_RATIO_THRESHOLD):
                COUNTER += 1
                #If no. of frames is greater than threshold frames,
                if COUNTER >= EYE_ASPECT_RATIO_CONSEC_FRAMES:
                    pygame.mixer.music.play(-1)
                    cv2.putText(frame, "You are Drowsy", (150,200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 2)
            else:
                pygame.mixer.music.stop()
                COUNTER = 0

        #Show video feed
        cv2.imshow('Video', frame)
        if(cv2.waitKey(1) & 0xFF == ord('q')):
            break

    #Finally when video capture is over, release the video capture and destroyAllWindows
    video_capture.release()
    cv2.destroyAllWindows()

print('lane detection')

#importing some useful packages
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import cv2
import os
from moviepy.editor import VideoFileClip
from IPython.display import HTML
import math
%matplotlib inline

def lane():
    def grayscale(img):
        """Applies the Grayscale transform
        This will return an image with only one color channel
        but NOTE: to see the returned image as grayscale
        (assuming your grayscaled image is called 'gray')
        you should call plt.imshow(gray, cmap='gray')"""
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Or use BGR2GRAY if you read an image with cv2.imread()
        # return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def canny(img, low_threshold, high_threshold):
        """Applies the Canny transform"""
        return cv2.Canny(img, low_threshold, high_threshold)

    def gaussian_blur(img, kernel_size):
        """Applies a Gaussian Noise kernel"""
        return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)

    def region_of_interest(img, vertices):
        """
        Applies an image mask.

        Only keeps the region of the image defined by the polygon
        formed from `vertices`. The rest of the image is set to black.
        """
        #defining a blank mask to start with
        mask = np.zeros_like(img)   

        #defining a 3 channel or 1 channel color to fill the mask with depending on the input image
        if len(img.shape) > 2:
            channel_count = img.shape[2]  # i.e. 3 or 4 depending on your image
            ignore_mask_color = (255,) * channel_count
        else:
            ignore_mask_color = 255

        #filling pixels inside the polygon defined by "vertices" with the fill color    
        cv2.fillPoly(mask, vertices, ignore_mask_color)

        #returning the image only where mask pixels are nonzero
        masked_image = cv2.bitwise_and(img, mask)
        return masked_image

    #used below
    def get_slope(x1,y1,x2,y2):
        return (y2-y1)/(x2-x1)

    #thick red lines 
    def draw_lines(img, lines, color=[255, 0, 0], thickness=6):
        """workflow:
        1) examine each individual line returned by hough & determine if it's in left or right lane by its slope
        because we are working "upside down" with the array, the left lane will have a negative slope and right positive
        2) track extrema
        3) compute averages
        4) solve for b intercept 
        5) use extrema to solve for points
        6) smooth frames and cache
        """
        global cache
        global first_frame
        y_global_min = img.shape[0] #min will be the "highest" y value, or point down the road away from car
        y_max = img.shape[0]
        l_slope, r_slope = [],[]
        l_lane,r_lane = [],[]
        det_slope = 0.4
        α =0.2 
        #i got this alpha value off of the forums for the weighting between frames.
        #i understand what it does, but i dont understand where it comes from
        #much like some of the parameters in the hough function

        for line in lines:
            #1
            for x1,y1,x2,y2 in line:
                slope = get_slope(x1,y1,x2,y2)
                if slope > det_slope:
                    r_slope.append(slope)
                    r_lane.append(line)
                elif slope < -det_slope:
                    l_slope.append(slope)
                    l_lane.append(line)
            #2
            y_global_min = min(y1,y2,y_global_min)

        # to prevent errors in challenge video from dividing by zero
        if((len(l_lane) == 0) or (len(r_lane) == 0)):
            print ('no lane detected')
            return 1

        #3
        l_slope_mean = np.mean(l_slope,axis =0)
        r_slope_mean = np.mean(r_slope,axis =0)
        l_mean = np.mean(np.array(l_lane),axis=0)
        r_mean = np.mean(np.array(r_lane),axis=0)

        if ((r_slope_mean == 0) or (l_slope_mean == 0 )):
            print('dividing by zero')
            return 1



        #4, y=mx+b -> b = y -mx
        l_b = l_mean[0][1] - (l_slope_mean * l_mean[0][0])
        r_b = r_mean[0][1] - (r_slope_mean * r_mean[0][0])

        #5, using y-extrema (#2), b intercept (#4), and slope (#3) solve for x using y=mx+b
        # x = (y-b)/m
        # these 4 points are our two lines that we will pass to the draw function
        l_x1 = int((y_global_min - l_b)/l_slope_mean) 
        l_x2 = int((y_max - l_b)/l_slope_mean)   
        r_x1 = int((y_global_min - r_b)/r_slope_mean)
        r_x2 = int((y_max - r_b)/r_slope_mean)

        #6
        if l_x1 > r_x1:
            l_x1 = int((l_x1+r_x1)/2)
            r_x1 = l_x1
            l_y1 = int((l_slope_mean * l_x1 ) + l_b)
            r_y1 = int((r_slope_mean * r_x1 ) + r_b)
            l_y2 = int((l_slope_mean * l_x2 ) + l_b)
            r_y2 = int((r_slope_mean * r_x2 ) + r_b)
        else:
            l_y1 = y_global_min
            l_y2 = y_max
            r_y1 = y_global_min
            r_y2 = y_max

        current_frame = np.array([l_x1,l_y1,l_x2,l_y2,r_x1,r_y1,r_x2,r_y2],dtype ="float32")

        if first_frame == 1:
            next_frame = current_frame        
            first_frame = 0        
        else :
            prev_frame = cache
            next_frame = (1-α)*prev_frame+α*current_frame

        cv2.line(img, (int(next_frame[0]), int(next_frame[1])), (int(next_frame[2]),int(next_frame[3])), color, thickness)
        cv2.line(img, (int(next_frame[4]), int(next_frame[5])), (int(next_frame[6]),int(next_frame[7])), color, thickness)

        cache = next_frame


    def hough_lines(img, rho, theta, threshold, min_line_len, max_line_gap):
        """
        `img` should be the output of a Canny transform.

        Returns an image with hough lines drawn.
        """
        lines = cv2.HoughLinesP(img, rho, theta, threshold, np.array([]), minLineLength=min_line_len, maxLineGap=max_line_gap)
        line_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
        draw_lines(line_img,lines)
        return line_img

    # Python 3 has support for cool math symbols.

    def weighted_img(img, initial_img, α=0.8, β=1., λ=0.):
        """
        `img` is the output of the hough_lines(), An image with lines drawn on it.
        Should be a blank image (all black) with lines drawn on it.

        `initial_img` should be the image before any processing.

        The result image is computed as follows:

        initial_img * α + img * β + λ
        NOTE: initial_img and img must be the same shape!
        """
        return cv2.addWeighted(initial_img, α, img, β, λ)



    def process_image(image):

        global first_frame

        gray_image = grayscale(image)
        img_hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        #hsv = [hue, saturation, value]
        #more accurate range for yellow since it is not strictly black, white, r, g, or b

        lower_yellow = np.array([20, 100, 100], dtype = "uint8")
        upper_yellow = np.array([30, 255, 255], dtype="uint8")

        mask_yellow = cv2.inRange(img_hsv, lower_yellow, upper_yellow)
        mask_white = cv2.inRange(gray_image, 200, 255)
        mask_yw = cv2.bitwise_or(mask_white, mask_yellow)
        mask_yw_image = cv2.bitwise_and(gray_image, mask_yw)

        kernel_size = 5
        gauss_gray = gaussian_blur(mask_yw_image,kernel_size)

        #same as quiz values
        low_threshold = 50
        high_threshold = 150
        canny_edges = canny(gauss_gray,low_threshold,high_threshold)

        imshape = image.shape
        lower_left = [imshape[1]/9,imshape[0]]
        lower_right = [imshape[1]-imshape[1]/9,imshape[0]]
        top_left = [imshape[1]/2-imshape[1]/8,imshape[0]/2+imshape[0]/10]
        top_right = [imshape[1]/2+imshape[1]/8,imshape[0]/2+imshape[0]/10]
        vertices = [np.array([lower_left,top_left,top_right,lower_right],dtype=np.int32)]
        roi_image = region_of_interest(canny_edges, vertices)

        #rho and theta are the distance and angular resolution of the grid in Hough space
        #same values as quiz
        rho = 4
        theta = np.pi/180
        #threshold is minimum number of intersections in a grid for candidate line to go to output
        threshold = 30
        min_line_len = 100
        max_line_gap = 180
        #my hough values started closer to the values in the quiz, but got bumped up considerably for the challenge video

        line_image = hough_lines(roi_image, rho, theta, threshold, min_line_len, max_line_gap)
        result = weighted_img(line_image, image, α=0.8, β=1., λ=0.)
        return result

    for source_img in os.listdir("test_images/"):
        first_frame = 1
        image = mpimg.imread("test_images/"+source_img)
        processed = process_image(image)
        mpimg.imsave("out_images/annotated_"+source_img,processed)

    first_frame = 1
    white_output = 'white.mp4'
    clip1 = VideoFileClip("solidWhiteRight.mp4")
    white_clip = clip1.fl_image(process_image) #NOTE: this function expects color images!!
    %time white_clip.write_videofile(white_output, audio=False)

    HTML("""
    <video width="960" height="540" controls>
      <source src="{0}">
    </video>
    """.format(white_output))
    
 ***Test on Images
Run on single still frames***

first_frame = 1
yellow_output = 'yellow.mp4'
clip2 = VideoFileClip('solidYellowLeft.mp4')
yellow_clip = clip2.fl_image(process_image)
%time yellow_clip.write_videofile(yellow_output, audio=False)

HTML("""
<video width="960" height="540" controls>
  <source src="{0}">
</video>
""".format(yellow_output))


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.cm import rainbow
%matplotlib inline
import warnings
warnings.filterwarnings('ignore')
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import numpy as np 
import pandas as pd 
import matplotlib.pyplot as plt 
import seaborn as sns 
%matplotlib inline
from sklearn.ensemble import RandomForestClassifier 
from sklearn.linear_model import LogisticRegression 
def maintanance():
    main=pd.read_csv('maintain.csv')
    main.head()
    main.describe()
    columns=['last date','engine','breaks','output','model']
    main.columns
    x=main.drop(columns=['output'])
    y=main['output']
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size = 0.33, random_state = 0)
    model=RandomForestClassifier(n_estimators=100)
    model.fit(x_train,y_train)
    prediction=model.predict(x_test)
    score=accuracy_score(prediction,y_test)
    score
    predicted= model.predict([[8,10,2019,0,0,0]])
    predicted
    
from tkinter import *
top = Tk()
top.geometry('500x500')
#create lable
test= Label(top,
                   text ="test").place(x=40,
                                              y=50)
test_input_area=Entry(top,
                             width=30).place(x=130,
                                            y=50)
btn =Button(top,text='submit!',bd='5').place(x=180,
                                            y=250)
result= Label(top,
                   text ="cat ordog").place(x=400
                                            ,
                                              y=350)
result_input_area=Entry(top,
                             width=30).place(x=130,
                                            y=350)
top.mainloop()

from tkinter import*
root=Tk()
root.geometry("500x500")
Label (root,text="Click on the option you want to select!!",fg="black",font=("calibri",20)).place(x=40,y=50)
Button(root,text="drowsiness detection",command=lambda:drow(root),font=("calibri",20),fg="blue",bg="yellow").place(x=130,y=100)
Button(root,text="lane detection",command=lambda:lane(),font=("calibri",20),fg="blue",bg="yellow").place(x=160,y=180)
Button(root,text="vechile Maintanance",command=lambda:gui(root),font=("calibri",20),fg="blue",bg="yellow").place(x=130,y=260)
root.mainloop()

from tkinter import*
root=Tk()
root.geometry("500x500")
Label(root,text="Fill all the details and click on submit for result!!").place(x=80,y=10)
Label(root,text ="Date").place(x=40,y=50)
Entry(root,width=30).place(x=130,y=50)
Label(root,text ="Month").place(x=40,y=100)
Entry(root,width=30).place(x=130,y=100) 
Label(root,text ="Year").place(x=40,y=150)
Entry(root,width=30).place(x=130,y=150)
Label(root,text ="Engine").place(x=40,y=200)
Entry(root,width=30).place(x=130,y=200)
Label(root,text ="Breaks").place(x=40,y=250)
Entry(root,width=30).place(x=130,y=250)
Label(root,text ="Model").place(x=40,y=300)
Entry(root,width=30).place(x=130,y=300)
Button(root,text='submit!',bd='5').place(x=180,y=350)
Label(root,text="result").place(x=40,y=450)
Entry(root,width=30).place(x=130,y=450)
root.mainloop()
