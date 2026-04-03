import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ActivityIndicator } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Location from 'expo-location';
import * as ImageManipulator from 'expo-image-manipulator';
import { Ionicons } from '@expo/vector-icons';
import { colors, fonts, borderRadius, spacing } from '../lib/theme';

interface GPSCameraPayload {
  photo_base64: string;
  gps_lat: number;
  gps_lng: number;
  capture_timestamp_ms: number;
}

interface GPSCameraProps {
  onCapture: (payload: GPSCameraPayload) => void;
  onCancel: () => void;
}

export default function GPSCamera({ onCapture, onCancel }: GPSCameraProps) {
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [hasLocationPermission, setHasLocationPermission] = useState<boolean | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const cameraRef = useRef<CameraView>(null);
  const isMounted = useRef(true); // Vuln C: Track mount state to prevent race condition crashes

  // Vuln C: Cleanup — mark unmounted so async callbacks abort safely
  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  useEffect(() => {
    (async () => {
      // 1. Request Camera Permissions
      if (!cameraPermission?.granted) {
        await requestCameraPermission();
      }
      // 2. Request Location Permissions
      const locationStatus = await Location.requestForegroundPermissionsAsync();
      if (isMounted.current) {
        setHasLocationPermission(locationStatus.status === 'granted');
      }
    })();
  }, [cameraPermission, requestCameraPermission]);

  const handleCapture = async () => {
    if (!cameraRef.current || isProcessing) return;

    setIsProcessing(true);
    try {
      // First fetch the hardware location
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Highest,
      });

      // Vuln C: Abort if component unmounted during GPS acquisition
      if (!isMounted.current) return;

      // Immediately capture the photo with EXIF data
      const photo = await cameraRef.current.takePictureAsync({
        exif: true,
        quality: 0.7,
      });

      if (!photo) throw new Error("Failed to capture photo");

      // Vuln C: Abort if component unmounted during photo capture
      if (!isMounted.current) return;

      // Compress and resize image to prevent 10MB+ payload bloat
      const manipResult = await ImageManipulator.manipulateAsync(
        photo.uri,
        [{ resize: { width: 640 } }],
        { compress: 0.5, format: ImageManipulator.SaveFormat.JPEG, base64: true }
      );

      if (!manipResult.base64) throw new Error("Failed to encode photo to base64");

      // Vuln C: Final mount check before delivering payload to parent
      if (!isMounted.current) return;

      // Bundle and return the secure payload
      onCapture({
        photo_base64: manipResult.base64,
        gps_lat: location.coords.latitude,
        gps_lng: location.coords.longitude,
        capture_timestamp_ms: Date.now(),
      });
    } catch (error) {
      console.error('Failed to capture GPS selfie:', error);
      if (isMounted.current) {
        setIsProcessing(false);
      }
    }
  };

  if (!cameraPermission || hasLocationPermission === null) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.statusText}>Requesting permissions...</Text>
      </View>
    );
  }

  if (!cameraPermission.granted || hasLocationPermission === false) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="warning" size={48} color={colors.error} />
        <Text style={styles.errorText}>
          Camera and Location permissions are required for Liveness Verification.
        </Text>
        <TouchableOpacity style={styles.cancelBtn} onPress={onCancel}>
          <Text style={styles.cancelBtnText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView 
        style={styles.camera} 
        facing="front"
        ref={cameraRef}
      >
        <View style={styles.overlay}>
          <View style={styles.header}>
            <TouchableOpacity style={styles.closeButton} onPress={onCancel}>
              <Ionicons name="close" size={28} color="#FFF" />
            </TouchableOpacity>
            <View style={styles.badge}>
              <Ionicons name="shield-checkmark" size={16} color={colors.primary} />
              <Text style={styles.badgeText}> Biometric Lock Active</Text>
            </View>
          </View>

          <View style={styles.frameContainer}>
            <View style={styles.faceFrame} />
            <Text style={styles.instructionText}>
              Proof of Liveness: Please show your face clearly in the frame
            </Text>
          </View>

          <View style={styles.controls}>
            {isProcessing ? (
              <View style={styles.processingContainer}>
                <ActivityIndicator size="large" color={colors.primary} />
                <Text style={styles.processingText}>Verifying Location & Liveness...</Text>
              </View>
            ) : (
              <TouchableOpacity style={styles.captureButton} onPress={handleCapture}>
                <View style={styles.captureButtonInner} />
              </TouchableOpacity>
            )}
          </View>
        </View>
      </CameraView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  statusText: {
    color: colors.text,
    marginTop: spacing.md,
    fontSize: fonts.sizes.md,
  },
  errorText: {
    color: colors.text,
    textAlign: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.xl,
    fontSize: fonts.sizes.lg,
  },
  cancelBtn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceLight,
  },
  cancelBtnText: {
    color: colors.text,
    fontSize: fonts.sizes.md,
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.3)',
    justifyContent: 'space-between',
    padding: spacing.lg,
    paddingTop: 50,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  closeButton: {
    padding: spacing.xs,
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderRadius: 20,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.pill,
    borderWidth: 1,
    borderColor: 'rgba(0, 201, 177, 0.3)',
  },
  badgeText: {
    color: '#FFF',
    fontSize: fonts.sizes.xs,
    fontWeight: '600',
  },
  frameContainer: {
    alignItems: 'center',
  },
  faceFrame: {
    width: 250,
    height: 350,
    borderWidth: 2,
    borderColor: colors.primary,
    borderStyle: 'dashed',
    borderRadius: 150,
    marginBottom: spacing.lg,
  },
  instructionText: {
    color: '#FFF',
    textAlign: 'center',
    fontSize: fonts.sizes.md,
    fontWeight: '500',
    backgroundColor: 'rgba(0,0,0,0.5)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  controls: {
    alignItems: 'center',
    height: 100,
    justifyContent: 'center',
  },
  captureButton: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: 'rgba(255,255,255,0.3)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureButtonInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#FFF',
  },
  processingContainer: {
    alignItems: 'center',
  },
  processingText: {
    color: '#FFF',
    marginTop: spacing.sm,
    fontSize: fonts.sizes.sm,
  },
});
