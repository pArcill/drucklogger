import { getAuthHeader } from './auth.js';

const API_BASE = window.__PRESSURE_API_BASE__ || 'http://localhost:8000/api';

// Cache for role hierarchy
let roleHierarchy = [];

/**
 * Fetch the available roles from the backend
 */
async function fetchRoles() {
	if (roleHierarchy.length > 0) {
		return roleHierarchy;
	}
	
	try {
		const response = await fetch(`${API_BASE}/config/roles`);
		if (response.ok) {
			const data = await response.json();
			roleHierarchy = data.roles || [];
		}
	} catch (error) {
		console.warn('Failed to fetch roles:', error);
	}
	
	return roleHierarchy;
}

/**
 * Populate clearance dropdowns with available roles
 */
async function populateRoleOptions() {
	const roles = await fetchRoles();
	
	if (roles.length === 0) {
		// Fallback to default roles if API call failed
		roles.push('guest', 'regular', 'elevated', 'full_clearance', 'top_secret');
	}
	
	const displayClearanceSelect = document.getElementById('displayClearance');
	const readingsClearanceSelect = document.getElementById('readingsClearance');
	
	// Populate display clearance dropdown
	if (displayClearanceSelect) {
		displayClearanceSelect.innerHTML = '';
		roles.forEach(role => {
			const option = document.createElement('option');
			option.value = role;
			option.textContent = role.replace(/_/g, ' ').charAt(0).toUpperCase() + role.replace(/_/g, ' ').slice(1);
			displayClearanceSelect.appendChild(option);
		});
		// Set default to 'regular'
		displayClearanceSelect.value = 'regular';
	}
	
	// Populate readings clearance dropdown
	if (readingsClearanceSelect) {
		readingsClearanceSelect.innerHTML = '';
		roles.forEach(role => {
			const option = document.createElement('option');
			option.value = role;
			option.textContent = role.replace(/_/g, ' ').charAt(0).toUpperCase() + role.replace(/_/g, ' ').slice(1);
			readingsClearanceSelect.appendChild(option);
		});
		// Set default to 'regular'
		readingsClearanceSelect.value = 'regular';
	}
}

/**
 * Opens the add sensor modal
 */
export function openAddSensorModal() {
  const modal = document.getElementById('addSensorModal');
  if (modal) {
    modal.style.display = 'flex';
    // Reset form
    document.getElementById('addSensorForm').reset();
    clearAllErrors();
    document.querySelector('input[name="sensorType"][value="physical"]').checked = true;
    updateFormForSensorType();
  }
}

/**
 * Closes the add sensor modal
 */
export function closeAddSensorModal() {
  const modal = document.getElementById('addSensorModal');
  if (modal) {
    modal.style.display = 'none';
    document.getElementById('addSensorForm').reset();
    clearAllErrors();
  }
}

/**
 * Updates form visibility based on selected sensor type
 */
export function updateFormForSensorType() {
  const sensorType = document.querySelector('input[name="sensorType"]:checked').value;
  // Currently both types use the same form, but this allows for future customization
}

/**
 * Validates MAC address format
 */
function isValidMacAddress(mac) {
  const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
  return macRegex.test(mac);
}

/**
 * Validates the form inputs
 */
function validateForm(formData) {
  const errors = {};

  // Validate name
  if (!formData.name || formData.name.trim().length === 0) {
    errors.name = 'Sensor name is required';
  }

  // Validate MAC address
  if (!formData.mac || !isValidMacAddress(formData.mac)) {
    errors.mac = 'Invalid MAC address format (use AA:BB:CC:DD:EE:FF)';
  }

  // Validate latitude
  const lat = parseFloat(formData.latitude);
  if (isNaN(lat) || lat < -90 || lat > 90) {
    errors.latitude = 'Latitude must be between -90 and 90';
  }

  // Validate longitude
  const lng = parseFloat(formData.longitude);
  if (isNaN(lng) || lng < -180 || lng > 180) {
    errors.longitude = 'Longitude must be between -180 and 180';
  }

  // Validate altitude
  const alt = parseFloat(formData.altitude);
  if (isNaN(alt)) {
    errors.altitude = 'Altitude must be a valid number';
  }

  // Validate battery
  const battery = parseFloat(formData.battery);
  if (isNaN(battery) || battery < 0 || battery > 100) {
    errors.battery = 'Battery must be between 0 and 100';
  }

  // Validate pressure range
  const pressureMin = parseFloat(formData.pressureMin);
  const pressureMax = parseFloat(formData.pressureMax);
  
  if (isNaN(pressureMin) || isNaN(pressureMax)) {
    if (isNaN(pressureMin)) {
      errors.pressureMin = 'Pressure range minimum must be a valid number';
    }
    if (isNaN(pressureMax)) {
      errors.pressureMax = 'Pressure range maximum must be a valid number';
    }
  } else if (pressureMin >= pressureMax) {
    errors.pressureMax = 'Maximum pressure must be greater than minimum';
  }

  return errors;
}

/**
 * Clears all form errors
 */
function clearAllErrors() {
  document.querySelectorAll('.form-error').forEach(el => {
    el.textContent = '';
  });
  const alert = document.getElementById('sensorFormAlert');
  if (alert) {
    alert.style.display = 'none';
    alert.textContent = '';
  }
}

/**
 * Display validation errors on the form
 */
function displayErrors(errors) {
  clearAllErrors();
  
  const fields = {
    'name': 'nameError',
    'mac': 'macError',
    'latitude': 'latError',
    'longitude': 'lngError',
    'altitude': 'altError',
    'battery': 'batteryError',
    'pressureMin': 'pressureMinError',
    'pressureMax': 'pressureMaxError'
  };

  Object.entries(errors).forEach(([field, message]) => {
    const errorElementId = fields[field];
    if (errorElementId) {
      const errorElement = document.getElementById(errorElementId);
      if (errorElement) {
        errorElement.textContent = message;
      }
    }
  });
}

/**
 * Shows an alert message in the form
 */
function showFormAlert(message, type = 'error') {
  const alert = document.getElementById('sensorFormAlert');
  if (alert) {
    alert.textContent = message;
    alert.className = `form-alert ${type}`;
    alert.style.display = 'block';
  }
}

/**
 * Handles the add sensor form submission
 */
export async function handleAddSensorSubmit(event) {
  event.preventDefault();

  const form = event.target;
  const formData = {
    sensorType: document.querySelector('input[name="sensorType"]:checked').value,
    name: document.getElementById('sensorName').value,
    mac: document.getElementById('sensorMac').value,
    latitude: document.getElementById('sensorLatitude').value,
    longitude: document.getElementById('sensorLongitude').value,
    altitude: document.getElementById('sensorAltitude').value || '0',
    battery: document.getElementById('sensorBattery').value,
    pressureMin: document.getElementById('pressureRangeMin').value,
    pressureMax: document.getElementById('pressureRangeMax').value,
    displayClearance: document.getElementById('displayClearance').value,
    readingsClearance: document.getElementById('readingsClearance').value
  };

  // Validate form
  const errors = validateForm(formData);
  if (Object.keys(errors).length > 0) {
    displayErrors(errors);
    return;
  }

  // Show loading state
  const submitBtn = form.querySelector('button[type="submit"]');
  const originalText = submitBtn.textContent;
  submitBtn.disabled = true;
  submitBtn.textContent = 'Creating sensor...';

  try {
    clearAllErrors();
    
    const payload = {
      sensor_type: formData.sensorType,
      name: formData.name,
      mac_address: formData.mac,
      latitude: parseFloat(formData.latitude),
      longitude: parseFloat(formData.longitude),
      altitude: parseFloat(formData.altitude),
      battery_level: parseFloat(formData.battery) / 100, // Convert from 0-100 to 0-1
      pressure_range_min: parseFloat(formData.pressureMin),
      pressure_range_max: parseFloat(formData.pressureMax),
      display_clearance: formData.displayClearance,
      readings_clearance: formData.readingsClearance
    };

    const response = await fetch(`${API_BASE}/sensors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': getAuthHeader()
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Failed to create sensor');
    }

    showFormAlert(`${formData.sensorType.charAt(0).toUpperCase() + formData.sensorType.slice(1)} sensor "${formData.name}" created successfully!`, 'success');
    
    // Close modal after a short delay
    setTimeout(() => {
      closeAddSensorModal();
      // Trigger a refresh of the sensor list
      const refreshBtn = document.querySelector('[data-action="refresh"]');
      if (refreshBtn) {
        refreshBtn.click();
      }
    }, 1500);

  } catch (error) {
    console.error('Error creating sensor:', error);
    showFormAlert(error.message || 'An error occurred while creating the sensor', 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalText;
  }
}

/**
 * Initialize the add sensor modal event listeners
 */
export function initAddSensorModal() {
  const addSensorBtn = document.querySelector('[data-action="add-sensor"]');
  if (addSensorBtn) {
    addSensorBtn.addEventListener('click', openAddSensorModal);
  }

  // Close modal when clicking outside
  const modal = document.getElementById('addSensorModal');
  if (modal) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeAddSensorModal();
      }
    });
  }

  // Prevent closing when clicking on modal content
  const modalContent = document.querySelector('.modal__content');
  if (modalContent) {
    modalContent.addEventListener('click', (event) => {
      event.stopPropagation();
    });
  }
  
  // Populate role options from backend
  populateRoleOptions();
}
