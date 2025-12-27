/**
 * Animated Logo Component
 * =======================
 * WebGL-based animated circular logo with smooth color transitions.
 * Uses SlideFinder brand colors with flowing blob animation.
 * 
 * @module components/animated-logo
 */

'use strict';

// WebGL Shaders
const VERTEX_SHADER = `
attribute vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `
precision highp float;
uniform float u_time;
uniform float u_heat;
uniform vec2 u_resolution;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution.xy;
    
    // Center the coordinates
    vec2 center = vec2(0.5, 0.5);
    float dist = length(uv - center);
    
    // Create circular mask - hard edge, no border
    float circle = step(dist, 0.5);
    
    // SlideFinder brand colors: #0078D4 (blue), #00BCF2 (cyan), #7FBA00 (green)
    vec3 blue = vec3(0.0, 0.471, 0.831);    // #0078D4
    vec3 cyan = vec3(0.0, 0.737, 0.949);    // #00BCF2
    vec3 green = vec3(0.498, 0.729, 0.0);   // #7FBA00
    
    float speed = 0.5 + u_heat * 0.8;
    float time = u_time * speed;
    
    // Vertical gradient from top (blue) to bottom (green)
    float t = uv.y;
    
    // Add flowing wave distortion
    t += sin(uv.x * 4.0 + time) * 0.08;
    t += cos(uv.x * 2.5 - time * 0.7) * 0.06;
    t += sin(time * 0.5) * 0.05;
    
    // Clamp and create smooth 3-color gradient
    t = clamp(t, 0.0, 1.0);
    
    vec3 color;
    if (t > 0.5) {
        color = mix(cyan, blue, (t - 0.5) * 2.0);
    } else {
        color = mix(green, cyan, t * 2.0);
    }
    
    // Apply circular mask
    gl_FragColor = vec4(color * circle, circle);
}`;

/**
 * Creates a WebGL shader
 * @param {WebGLRenderingContext} gl - WebGL context
 * @param {number} type - Shader type
 * @param {string} source - Shader source code
 * @returns {WebGLShader|null} Compiled shader or null on error
 */
function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    if (!shader) return null;
    
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('[AnimatedLogo] Shader compile failed:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
    }
    return shader;
}

/**
 * AnimatedLogo class - WebGL animated circular logo
 */
export class AnimatedLogo {
    /**
     * @param {HTMLElement} container - Container element for the logo
     * @param {Object} options - Configuration options
     * @param {number} [options.size=64] - Size in pixels
     * @param {number} [options.heat=0] - Animation intensity (0-1)
     * @param {boolean} [options.animated=true] - Whether to animate
     */
    constructor(container, options = {}) {
        this.container = container;
        this.size = options.size || 64;
        this.heat = options.heat || 0;
        this.targetHeat = this.heat;
        this.animated = options.animated !== false;
        
        this.canvas = null;
        this.gl = null;
        this.program = null;
        this.uniforms = { time: null, resolution: null, heat: null };
        this.animationId = null;
        this.startTime = Date.now();
        
        this.init();
    }
    
    /**
     * Initialize the WebGL canvas and context
     */
    init() {
        // Create wrapper div
        this.wrapper = document.createElement('div');
        this.wrapper.className = 'animated-logo-wrapper';
        this.wrapper.style.cssText = `
            width: ${this.size}px;
            height: ${this.size}px;
            border-radius: 50%;
            overflow: hidden;
            transition: filter 0.5s ease;
        `;
        
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = `
            width: 100%;
            height: 100%;
            display: block;
        `;
        
        this.wrapper.appendChild(this.canvas);
        this.container.appendChild(this.wrapper);
        
        // Initialize WebGL
        if (!this.initGL()) {
            console.warn('[AnimatedLogo] WebGL not available, falling back to static logo');
            this.showFallback();
            return;
        }
        
        this.resize();
        
        if (this.animated) {
            this.render();
        } else {
            this.renderOnce();
        }
    }
    
    /**
     * Initialize WebGL context and shaders
     * @returns {boolean} Success status
     */
    initGL() {
        const gl = this.canvas.getContext('webgl', {
            alpha: true,
            premultipliedAlpha: false,
            preserveDrawingBuffer: true
        });
        
        if (!gl) return false;
        this.gl = gl;
        
        // Create shaders
        const vertShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
        const fragShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
        if (!vertShader || !fragShader) return false;
        
        // Create program
        const program = gl.createProgram();
        if (!program) return false;
        
        gl.attachShader(program, vertShader);
        gl.attachShader(program, fragShader);
        gl.linkProgram(program);
        
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            console.error('[AnimatedLogo] Program link failed:', gl.getProgramInfoLog(program));
            return false;
        }
        
        this.program = program;
        gl.useProgram(program);
        
        // Setup geometry (fullscreen quad)
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
            -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1
        ]), gl.STATIC_DRAW);
        
        const positionLoc = gl.getAttribLocation(program, 'position');
        gl.enableVertexAttribArray(positionLoc);
        gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);
        
        // Get uniform locations
        this.uniforms = {
            time: gl.getUniformLocation(program, 'u_time'),
            resolution: gl.getUniformLocation(program, 'u_resolution'),
            heat: gl.getUniformLocation(program, 'u_heat')
        };
        
        // Enable blending for transparency
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        
        return true;
    }
    
    /**
     * Resize canvas to match display size
     */
    resize() {
        if (!this.canvas || !this.gl) return;
        
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = this.size * dpr;
        this.canvas.height = this.size * dpr;
        
        this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    }
    
    /**
     * Render animation frame
     */
    render = () => {
        if (!this.gl || !this.uniforms.time) return;
        
        // Smooth heat transition
        this.heat += (this.targetHeat - this.heat) * 0.01;
        
        const time = (Date.now() - this.startTime) * 0.001;
        this.gl.uniform1f(this.uniforms.time, time);
        this.gl.uniform1f(this.uniforms.heat, this.heat);
        this.gl.uniform2f(this.uniforms.resolution, this.canvas.width, this.canvas.height);
        
        this.gl.clearColor(0, 0, 0, 0);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.drawArrays(this.gl.TRIANGLES, 0, 6);
        
        if (this.animated) {
            this.animationId = requestAnimationFrame(this.render);
        }
    };
    
    /**
     * Render single frame (non-animated mode)
     */
    renderOnce() {
        if (!this.gl || !this.uniforms.time) return;
        
        const time = (Date.now() - this.startTime) * 0.001;
        this.gl.uniform1f(this.uniforms.time, time);
        this.gl.uniform1f(this.uniforms.heat, this.heat);
        this.gl.uniform2f(this.uniforms.resolution, this.canvas.width, this.canvas.height);
        
        this.gl.clearColor(0, 0, 0, 0);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.drawArrays(this.gl.TRIANGLES, 0, 6);
    }
    
    /**
     * Set heat level (animation intensity)
     * @param {number} heat - Heat value (0-1)
     */
    setHeat(heat) {
        this.targetHeat = Math.max(0, Math.min(1, heat));
        
        // Update glow based on heat
        const glowIntensity = 15 + heat * 20;
        const glowOpacity = 0.3 + heat * 0.3;
        this.wrapper.style.filter = `drop-shadow(0 0 ${glowIntensity}px rgba(0, 188, 242, ${glowOpacity}))`;
    }
    
    /**
     * Set logo size
     * @param {number} size - Size in pixels
     */
    setSize(size) {
        this.size = size;
        this.wrapper.style.width = `${size}px`;
        this.wrapper.style.height = `${size}px`;
        this.resize();
    }
    
    /**
     * Show fallback static logo (when WebGL unavailable)
     */
    showFallback() {
        this.wrapper.innerHTML = `
            <svg width="${this.size}" height="${this.size}" viewBox="0 0 100 100">
                <defs>
                    <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#0078D4" />
                        <stop offset="50%" stop-color="#00BCF2" />
                        <stop offset="100%" stop-color="#7FBA00" />
                    </linearGradient>
                </defs>
                <circle cx="50" cy="50" r="45" fill="url(#logoGradient)" />
            </svg>
        `;
    }
    
    /**
     * Start animation
     */
    start() {
        if (!this.animated) {
            this.animated = true;
            this.render();
        }
    }
    
    /**
     * Stop animation
     */
    stop() {
        this.animated = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.stop();
        if (this.wrapper && this.wrapper.parentNode) {
            this.wrapper.parentNode.removeChild(this.wrapper);
        }
    }
}

/**
 * Initialize animated logo on the hero section
 */
export function initAnimatedLogo() {
    const heroContent = document.querySelector('.hero-content');
    if (!heroContent) return null;
    
    // Remove existing static logo if present
    const existingLogo = heroContent.querySelector('.hero-logo');
    if (existingLogo) {
        existingLogo.style.display = 'none';
    }
    
    // Create container for animated logo
    const logoContainer = document.createElement('div');
    logoContainer.className = 'hero-logo-container';
    logoContainer.setAttribute('aria-hidden', 'true');
    
    // Insert before the h1.logo
    const h1Logo = heroContent.querySelector('.logo');
    if (h1Logo) {
        heroContent.insertBefore(logoContainer, h1Logo);
    } else {
        heroContent.prepend(logoContainer);
    }
    
    // Create animated logo
    const animatedLogo = new AnimatedLogo(logoContainer, {
        size: 200,
        heat: 0,
        animated: true
    });
    
    // Make it globally accessible for other modules to control
    window.slideFinderLogo = animatedLogo;
    
    return animatedLogo;
}

export default AnimatedLogo;
