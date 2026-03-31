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
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
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
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
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

function logout() {
  clearAuth();
  showAuthScreen();
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
          await login(username, password);
          showDashboard();
        } catch (error) {
          showAuthError(error.message);
          submitBtn.disabled = false;
        }
      }, 1500);
    } else {
      await login(username, password);
      showDashboard();
    }
  } catch (error) {
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
  updateUserInfo
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
