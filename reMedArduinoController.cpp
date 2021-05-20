/* Code for controlling the Arduino components in the ReMed system.
 */


// Libraries
#include <Q2HX711.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Constants
const byte hx711_data_pin = 2;
const byte hx711_clock_pin = 3;
const int buzzer = 9;

// Variables
float y1 = 82.0; // calibrated mass to be added
long x1 = 8389299L;
long x0 = 8356082L;
float avg_size = 10.0; // amount of averages for each mass measurement
float mass = -1000;
int buzz; // this increments so the buzzer only fires every 10 seconds
int loopTimes = 0; // tracks the reminder system so it doesn't continue for more than 1 hour
Q2HX711 hx711(hx711_data_pin, hx711_clock_pin); // prep hx711
LiquidCrystal_I2C lcd = LiquidCrystal_I2C(0x27, 16, 2); // lcd screen

void setup() {

  Serial.begin(9600); // prepare serial port
  delay(1000); // allow load cell and hx711 to settle
  getMass(); // set initial value for the mass from the weight sensor
  pinMode(buzzer, OUTPUT); // set the buzzer pin 9 as an output
  buzz = 0; // setting the initial value for the buzzer
  lcd.init(); // initialise the LCD screen 
  Serial.write(18);

}

void loop() {
  
  if (Serial.available() > 0) {  // if we get a valid byte, run program

    int inByte = Serial.read() - '0'; // get byte command from RPi

    switch (inByte) 
    {
      // begin LCD alert for user to take their medication
      case 1: 
        medicationAlertLCD(1); 
        while (mass > 41.0) {
          medicationAlertBuzz(buzz);
          getMass();
          delay(500);
          loopTimes++;
          if (loopTimes >= 3600) {
            Serial.write(38); // Reports to the Rpi the medication was forgotten
            break; // ends the alert system after 1 hour of waiting
          }
        }
        if (loopTimes < 3600) {
          Serial.write(28); // Reports to the Rpi the cup was lifted
        }
        break;
        //if the Rpi reports the cup is not empty, display that to the LCD
      case 2: 
        medicationAlertLCD(4); // code 4 clears the screen
        medicationAlertLCD(2);
        delay(2000);
        break;
        //If the RPi reports the cup is empty, display a message
      case 3: 
        medicationAlertLCD(4);
        medicationAlertLCD(3);
        delay(10000); // Display the message for 10 seconds
        medicationAlertLCD(4);
        break;
    }  
  }
}

void getMass() {
  // averaging reading
  long reading = 0;
  for (int jj=0;jj<int(avg_size);jj++){
    reading+=hx711.read();
  }
  reading/=long(avg_size);

  // calculating mass based on calibration and linear fit
  float ratio_1 = (float) (reading-x0);
  float ratio_2 = (float) (x1-x0);
  float ratio = ratio_1/ratio_2;
  mass = y1*ratio;
}

void medicationAlertLCD(int displayCommand) {
  switch (displayCommand) {
  case 1:
    lcd.backlight();
    lcd.setCursor(2,0);
    lcd.print("Time for your");
    lcd.setCursor(3,1);
    lcd.print("medication");
    break;
  case 2:
    lcd.backlight();
    lcd.setCursor(0,0);
    lcd.print("Cup isn't empty!");
    lcd.setCursor(2,1);
    lcd.print("Check again.");
    break;
  case 3:
    lcd.backlight();
    lcd.setCursor(0,0);
    lcd.print("Have a great day");
    lcd.setCursor(3,1);
    lcd.print("~ ReMed ~");
    break;
  case 4:
    lcd.clear();
    break;
  }

}

void medicationAlertBuzz(int turn) {
  if (turn == 0) {
    tone(buzzer, 500);
    delay(250);
    tone(buzzer, 1200);
    delay(250);
    noTone(buzzer);
  }
  buzz++;
  Serial.println(buzz);
  if (buzz == 10) {
    buzz = 0;
  } // tone only runs every 10 seconds
}
