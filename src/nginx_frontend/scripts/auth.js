// Authentication logic
const API_BASE = window.__PRESSURE_API_BASE__ || 'http://localhost:8000/api';

const authState = {
  token: localStorage.getItem('auth_token'),
  user: JSON.parse(localStorage.getItem('auth_user') || 'null'),
  isAuthenticated: !!localStorage.getItem('auth_token'),
  isRegisterMode: false
};

function setAuthToken(token) {
  authState.token = token;
  localStorage.setItem('auth_token', token);
}

function setAuthUser(user) {
  authState.user = user;
  localStorage.setItem('auth_user', JSON.stringify(user));
}

function clearAuth() {
  authState.token = null;
  authState.user = null;
  authState.isAuthenticated = false;
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
}

async function register(username, email, password) {
  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        email,
        password
      })
    });

    if (!response.ok) {
      // Try to parse error response as JSON, but handle non-JSON responses (like nginx error pages)
      let errorMessage = 'Registration failed';
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const error = await response.json();
          errorMessage = error.detail || 'Registration failed';
        } else {
          errorMessage = `Registration failed with status ${response.status}. Backend may be unavailable or overloaded.`;
          console.warn(`Received non-JSON error response with status ${response.status}:`, response.statusText);
        }
      } catch (parseError) {
        errorMessage = `Registration failed with status ${response.status}. Backend may be experiencing issues.`;
        console.warn('Error parsing response:', parseError);
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
    console.error('Registration error:', error);
    throw error;
  }
}

async function login(username, password) {
  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password
      })
    });

    if (!response.ok) {
      // Try to parse error response as JSON, but handle non-JSON responses (like nginx error pages)
      let errorMessage = 'Login failed';
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const error = await response.json();
          errorMessage = error.detail || 'Login failed';
        } else {
          // Response is not JSON (e.g., HTML error page from nginx)
          errorMessage = `Login failed with status ${response.status}. Backend may be unavailable or overloaded.`;
          console.warn(`Received non-JSON error response with status ${response.status}:`, response.statusText);
        }
      } catch (parseError) {
        errorMessage = `Login failed with status ${response.status}. Backend may be experiencing issues.`;
        console.warn('Error parsing response:', parseError);
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    setAuthToken(data.access_token);
    setAuthUser(data.user);
    authState.isAuthenticated = true;

    return data;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

async function refreshUserProfile() {
  try {
    const authHeader = getAuthHeader();
    console.log('refreshUserProfile: auth header present?', !!authHeader);
    if (!authHeader) {
      console.log('refreshUserProfile: no auth header, returning');
      return;
    }
    
    console.log('refreshUserProfile: fetching from', `${API_BASE}/auth/me`);
    const response = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
      }
    });

    console.log('refreshUserProfile: response status', response.status);
    if (!response.ok) {
      if (response.status === 401) {
        console.log('refreshUserProfile: 401 - clearing auth');
        // Token expired, logout
        clearAuth();
        return null;
      }
      throw new Error(`Failed to refresh profile: ${response.status}`);
    }

    const user = await response.json();
    console.log('refreshUserProfile: got user', user.username, 'with role', user.role);
    setAuthUser(user);
    if (typeof updateUserInfo === 'function') {
      updateUserInfo();
    }
    return user;
  } catch (error) {
    console.warn('Failed to refresh user profile:', error);
    return null;
  }
}

function logout() {
  console.log('Logout: starting');
  
  // Clean up app before logging out
  if (typeof window.cleanupApp === 'function') {
    console.log('Logout: calling cleanupApp');
    window.cleanupApp();
    console.log('Logout: cleanupApp completed');
  } else {
    console.warn('Logout: cleanupApp not available on window');
  }
  
  console.log('Logout: clearing auth');
  clearAuth();
  
  console.log('Logout: resetting to login mode');
  // If we're in register mode, toggle back to login mode
  if (authState.isRegisterMode) {
    authState.isRegisterMode = true; // Set to true so toggleAuthMode will set it to false
    toggleAuthMode();
  } else {
    // Even if not in register mode, ensure the form UI is in login mode
    const emailGroup = document.getElementById('emailGroup');
    const screenMode = document.getElementById('authScreenMode');
    const submitBtn = document.getElementById('authSubmitBtn');
    const togglePrompt = document.getElementById('authTogglePrompt');
    const toggleLink = document.getElementById('authToggleLink');
    
    emailGroup.style.display = 'none';
    screenMode.textContent = 'Sign in to your account';
    submitBtn.textContent = 'Sign in';
    togglePrompt.textContent = "Don't have an account?";
    toggleLink.textContent = 'Sign up';
    authState.isRegisterMode = false;
  }
  
  console.log('Logout: clearing form');
  // Clear the form
  clearAuthForm();
  
  console.log('Logout: showing auth screen');
  // Show the auth screen
  showAuthScreen();
  
  console.log('Logout: complete');
}

function getAuthHeader() {
  if (!authState.token) {
    return null;
  }
  return `Bearer ${authState.token}`;
}

function isAuthenticated() {
  return authState.isAuthenticated && authState.token !== null;
}

function getCurrentUser() {
  return authState.user;
}

function getCurrentUserRole() {
  return authState.user?.role || 'guest';
}

// UI Functions
function showAuthScreen() {
  document.getElementById('authScreen').style.display = 'flex';
  document.getElementById('dashboardScreen').style.display = 'none';
}

function showDashboard() {
  document.getElementById('authScreen').style.display = 'none';
  document.getElementById('dashboardScreen').style.display = 'flex';
  updateUserInfo();
}

function toggleAuthMode() {
  authState.isRegisterMode = !authState.isRegisterMode;
  const emailGroup = document.getElementById('emailGroup');
  const screenMode = document.getElementById('authScreenMode');
  const submitBtn = document.getElementById('authSubmitBtn');
  const togglePrompt = document.getElementById('authTogglePrompt');
  const toggleLink = document.getElementById('authToggleLink');
  
  if (authState.isRegisterMode) {
    emailGroup.style.display = 'flex';
    screenMode.textContent = 'Create a new account';
    submitBtn.textContent = 'Sign up';
    togglePrompt.textContent = 'Already have an account?';
    toggleLink.textContent = 'Sign in';
  } else {
    emailGroup.style.display = 'none';
    screenMode.textContent = 'Sign in to your account';
    submitBtn.textContent = 'Sign in';
    togglePrompt.textContent = "Don't have an account?";
    toggleLink.textContent = 'Sign up';
  }
  
  clearAuthForm();
}

function clearAuthForm() {
  document.getElementById('authForm').reset();
  document.getElementById('authAlert').style.display = 'none';
  document.getElementById('authSubmitBtn').disabled = false;
  clearFormErrors();
}

function clearFormErrors() {
  document.getElementById('usernameError').textContent = '';
  document.getElementById('emailError').textContent = '';
  document.getElementById('passwordError').textContent = '';
}

function showAuthError(message) {
  const alert = document.getElementById('authAlert');
  alert.className = 'auth-alert auth-alert--error';
  alert.textContent = message;
  alert.style.display = 'block';
}

function showAuthSuccess(message) {
  const alert = document.getElementById('authAlert');
  alert.className = 'auth-alert auth-alert--success';
  alert.textContent = message;
  alert.style.display = 'block';
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  clearFormErrors();
  
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;
  const submitBtn = document.getElementById('authSubmitBtn');
  
  // Disable button during submission
  submitBtn.disabled = true;
  
  try {
    if (authState.isRegisterMode) {
      const email = document.getElementById('authEmail').value.trim();
      if (!email) {
        throw new Error('Email is required');
      }
      const result = await register(username, email, password);
      showAuthSuccess('Account created! Signing you in...');
      
      // Auto-login after registration
      setTimeout(async () => {
        try {
          console.log('Auto-login: attempting login');
          await login(username, password);
          console.log('Auto-login: login successful');
          
          console.log('Auto-login: showing dashboard');
          showDashboard();
          
          // Initialize the app after login
          console.log('Auto-login: initializing app');
          if (typeof window.initializeApp === 'function') {
            await window.initializeApp();
            console.log('Auto-login: app initialized successfully');
          } else {
            console.warn('initializeApp not available on window');
          }
        } catch (error) {
          console.error('Auto-login failed:', error);
          showAuthError(`Login failed: ${error.message}`);
          submitBtn.disabled = false;
        }
      }, 1500);
    } else {
      console.log('Direct login: attempting login');
      await login(username, password);
      console.log('Direct login: login successful');
      
      console.log('Direct login: showing dashboard');
      showDashboard();
      
      // Initialize the app after login
      console.log('Direct login: initializing app');
      if (typeof window.initializeApp === 'function') {
        await window.initializeApp();
        console.log('Direct login: app initialized successfully');
      } else {
        console.warn('initializeApp not available on window');
      }
    }
  } catch (error) {
    console.error('Auth error:', error);
    showAuthError(error.message);
    submitBtn.disabled = false;
  }
}

function updateUserInfo() {
  const userInfo = document.getElementById('userInfo');
  if (authState.user) {
    userInfo.textContent = `${authState.user.username} (${authState.user.role})`;
  }
}

// Initialize on load
function initAuth() {
  if (isAuthenticated()) {
    showDashboard();
  } else {
    showAuthScreen();
  }
}

// ES6 Module exports
export {
  setAuthToken,
  setAuthUser,
  clearAuth,
  register,
  login,
  logout,
  getAuthHeader,
  isAuthenticated,
  getCurrentUser,
  getCurrentUserRole,
  initAuth,
  showAuthScreen,
  showDashboard,
  toggleAuthMode,
  clearAuthForm,
  showAuthError,
  showAuthSuccess,
  handleAuthSubmit,
  updateUserInfo,
  refreshUserProfile
};

// Also make functions globally available for inline event handlers
window.logout = logout;
window.toggleAuthMode = toggleAuthMode;
window.handleAuthSubmit = handleAuthSubmit;
window.getAuthHeader = getAuthHeader;
window.isAuthenticated = isAuthenticated;
window.getCurrentUser = getCurrentUser;
window.getCurrentUserRole = getCurrentUserRole;
window.initAuth = initAuth;
window.showAuthScreen = showAuthScreen;
window.showDashboard = showDashboard;
window.refreshUserProfile = refreshUserProfile;
