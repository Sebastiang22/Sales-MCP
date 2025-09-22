// sudo journalctl -u wha-api -f
// sudo systemctl restart87 wha-api
require('dotenv').config({ path: require('path').resolve(__dirname, '.env') });
const { 
    default: makeWASocket, 
    DisconnectReason, 
    useMultiFileAuthState, 
    downloadMediaMessage,
    isJidBroadcast,
    makeCacheableSignalKeyStore,
    fetchLatestBaileysVersion
} = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const axios = require('axios'); // Se utiliza para hacer solicitudes HTTP
const http = require('http');
const { Server } = require('socket.io');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const nodemailer = require('nodemailer');
const os = require('os');
const { execFile } = require('child_process');

// Configuración de Express y middleware
const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Crear servidor HTTP y configurar Socket.IO
// Toma el puerto base (PORT) y suma 10 para evitar colisión con index.js
const PORT = Number(process.env.PORT || 3006);
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

// =====================
// Email alerts (SMTP)
// =====================
const EMAIL_RECIPIENTS = 'lcastrov@unal.edu.co,sebastiangcoca@gmail.com,yeissoncalderonortiz@gmail.com,ciglesiaso@unal.edu.co';

const mailer = nodemailer.createTransport({
    host: process.env.EMAIL_HOST,
    port: Number(process.env.EMAIL_PORT || 587),
    secure: String(process.env.EMAIL_SECURE || 'false') === 'true',
    auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS
    }
});

// Verificar transporte en el arranque (no romper si falla)
mailer.verify()
    .then(() => console.log('📧 SMTP listo para enviar alertas'))
    .catch((err) => console.warn('⚠️ No se pudo verificar SMTP (continuando):', err?.message || err));

/**
 * Envía correo de alerta usando el transport configurado
 * @param {string} subject - Asunto del correo
 * @param {string} html - HTML del cuerpo
 */
async function sendAlertEmail(subject, html) {
    try {
        const from = process.env.EMAIL_FROM || process.env.EMAIL_USER;
        if (!from || !process.env.EMAIL_HOST || !process.env.EMAIL_USER) {
            console.warn('⚠️ Configuración SMTP incompleta. Se omite envío de correo.');
            return;
        }
        await mailer.sendMail({ from, to: EMAIL_RECIPIENTS, subject, html });
        console.log('📧 Alerta enviada:', subject);
    } catch (err) {
        console.error('❌ Error enviando correo de alerta:', err?.message || err);
    }
}

/**
 * Obtiene y cachea la última versión soportada por Baileys para WhatsApp Web
 * @returns {Promise<number[]>} Versión en formato [major, minor, patch]
 */
let cachedWaVersion = null;
async function getLatestWhatsAppVersion() {
    if (cachedWaVersion) return cachedWaVersion;
    try {
        const { version } = await fetchLatestBaileysVersion();
        cachedWaVersion = version;
        console.log(`🔧 Versión de WhatsApp Web detectada por Baileys: ${version.join('.')}`);
        return version;
    } catch (err) {
        console.warn('⚠️ No se pudo obtener la última versión de WhatsApp Web, se usará la predeterminada:', err?.message || err);
        return undefined;
    }
}

// Anti-spam / debounce 5 min
let waOutageActive = false;
let webhookOutageActive = false;
let lastEmailAt = 0;
const MIN_ALERT_INTERVAL_MS = 5 * 60 * 1000;

/**
 * Determina si se debe enviar correo ahora respetando un intervalo mínimo
 * @returns {boolean}
 */
function shouldEmailNow() {
    const now = Date.now();
    if (now - lastEmailAt > MIN_ALERT_INTERVAL_MS) {
        lastEmailAt = now;
        return true;
    }
    return false;
}

/**
 * Formatea la razón de desconexión a partir del objeto lastDisconnect de Baileys
 * @param {any} lastDisconnect
 * @returns {{ statusCode?: number, label: string, message: string, stack?: string }}
 */
function formatDisconnectReason(lastDisconnect) {
    try {
        const err = lastDisconnect?.error;
        const statusCode = err?.output?.statusCode;
        const message = err?.message || (typeof err?.toString === 'function' ? err.toString() : 'Desconocido');
        let label = 'Desconocido';

        switch (statusCode) {
            case DisconnectReason?.loggedOut:
                label = 'Sesión cerrada (loggedOut)';
                break;
            case DisconnectReason?.badSession:
                label = 'Sesión corrupta o inválida (badSession)';
                break;
            case DisconnectReason?.connectionClosed:
                label = 'Conexión cerrada (connectionClosed)';
                break;
            case DisconnectReason?.connectionLost:
                label = 'Conexión perdida (connectionLost)';
                break;
            case DisconnectReason?.connectionReplaced:
                label = 'Conexión reemplazada (connectionReplaced)';
                break;
            case DisconnectReason?.timedOut:
                label = 'Tiempo de espera excedido (timedOut)';
                break;
            case DisconnectReason?.multideviceMismatch:
                label = 'Conflicto multi-dispositivo (multideviceMismatch)';
                break;
            default:
                if (typeof statusCode === 'number') {
                    label = `Código ${statusCode}`;
                }
        }

        return { statusCode, label, message, stack: err?.stack };
    } catch (e) {
        return { statusCode: undefined, label: 'Desconocido', message: 'Sin detalles', stack: '' };
    }
}

// Configuración para múltiples sesiones
let globalSocket1 = null; // Primera sesión
let globalSocket2 = null; // Segunda sesión
let isConnecting1 = false; // Variable para controlar el estado de conexión de la primera sesión
let isConnecting2 = false; // Variable para controlar el estado de conexión de la segunda sesión
let reconnectAttempts1 = 0; // Contador de intentos de reconexión para la primera sesión
let reconnectAttempts2 = 0; // Contador de intentos de reconexión para la segunda sesión
const MAX_RECONNECT_ATTEMPTS = 5; // Máximo número de intentos de reconexión
const pdfFilePath = path.join(__dirname, 'MenuGopapa.pdf');

// Array global para almacenar mensajes entrantes (opcional)
let newMessages = [];

// Mapa para asociar teléfonos con la sesión que los contactó
// Clave: número sin sufijo (solo dígitos). Valor: nombre de sesión ('session1' | 'session2')
const phoneSessionMap = new Map();

/**
 * Verifica si un socket de WhatsApp está activo
 * @param {any} socket - Instancia de socket de Baileys
 * @returns {boolean} Verdadero si el socket está activo
 */
function isSocketActive(socket) {
    return Boolean(socket && socket.user);
}

/**
 * Obtiene el socket adecuado para entregar un mensaje/medio
 * Prioridad: sesión preferida -> sesión asociada al teléfono -> primera sesión activa disponible
 * @param {string} phoneNumber - Número de teléfono en dígitos (sin dominio)
 * @param {string|undefined} preferredSession - Nombre de sesión solicitado ('session1' | 'session2')
 * @returns {any|null} Instancia de socket o null si no hay sesiones activas
 */
function getSocketForDelivery(phoneNumber, preferredSession) {
    // Modo de una sola sesión: usar únicamente session1
    return isSocketActive(globalSocket1) ? globalSocket1 : null;
}

/**
 * Función para limpiar sesiones duplicadas y archivos de autenticación corruptos
 * @param {string} sessionName - Nombre de la sesión (session1 o session2)
 * @returns {Promise<void>}
 */
async function cleanupAuthFiles(sessionName) {
    try {
        const authDir = path.join(__dirname, `auth_info_baileys_${sessionName}`);
        if (!fs.existsSync(authDir)) {
            fs.mkdirSync(authDir, { recursive: true });
            console.log(`📁 Carpeta de autenticación creada (${sessionName}): ${authDir}`);
            return;
        }
        const files = fs.readdirSync(authDir);
        
        // Buscar archivos de sesión duplicados o corruptos
        const sessionFiles = files.filter(file => file.startsWith('session-'));
        const credsFile = path.join(authDir, 'creds.json');
        
        // Verificar si hay múltiples archivos de sesión para el mismo número
        const sessionNumbers = new Set();
        const duplicateSessions = [];
        
        sessionFiles.forEach(file => {
            const match = file.match(/session-(\d+)\.\d+\.json/);
            if (match) {
                const number = match[1];
                if (sessionNumbers.has(number)) {
                    duplicateSessions.push(file);
                } else {
                    sessionNumbers.add(number);
                }
            }
        });
        
        // Eliminar sesiones duplicadas (mantener la más reciente)
        for (const duplicate of duplicateSessions) {
            const filePath = path.join(authDir, duplicate);
            fs.unlinkSync(filePath);
            console.log(`🗑️ Sesión duplicada eliminada (${sessionName}): ${duplicate}`);
        }
        
        // Verificar integridad del archivo de credenciales
        if (fs.existsSync(credsFile)) {
            try {
                const credsContent = fs.readFileSync(credsFile, 'utf8');
                JSON.parse(credsContent);
                console.log(`✅ Archivo de credenciales válido (${sessionName})`);
            } catch (error) {
                console.log(`❌ Archivo de credenciales corrupto (${sessionName}), eliminando...`);
                fs.unlinkSync(credsFile);
            }
        }
        
        console.log(`🧹 Limpieza de archivos de autenticación completada (${sessionName})`);
    } catch (error) {
        console.error(`❌ Error durante la limpieza de archivos (${sessionName}):`, error.message);
    }
}

/**
 * Función para conectar a WhatsApp usando baileys para una sesión específica
 * @param {string} sessionName - Nombre de la sesión (session1 o session2)
 * @param {Object} socketVariable - Variable global del socket (globalSocket1 o globalSocket2)
 * @param {boolean} isConnectingVariable - Variable de control de conexión
 * @param {number} reconnectAttemptsVariable - Variable de intentos de reconexión
 * @returns {Promise<void>}
 */
async function connectToWhatsApp(sessionName, socketVariable, isConnectingVariable, reconnectAttemptsVariable) {
    // Evitar múltiples conexiones simultáneas
    if (isConnectingVariable) {
        console.log(`⚠️ Ya hay una conexión en progreso para ${sessionName}, esperando...`);
        return;
    }

    // Verificar si ya hay una conexión activa
    if (socketVariable && socketVariable.user) {
        console.log(`✅ Ya hay una conexión activa de WhatsApp para ${sessionName}`);
        return;
    }

    // Actualizar la variable de control de conexión
    if (sessionName === 'session1') {
        isConnecting1 = true;
    } else {
        isConnecting2 = true;
    }
    
    console.log(`🔄 Iniciando conexión a WhatsApp para ${sessionName}...`);

    try {
        // Limpiar archivos de autenticación antes de conectar
        await cleanupAuthFiles(sessionName);
        
        const { state, saveCreds } = await useMultiFileAuthState(`auth_info_baileys_${sessionName}`);
        const latestVersion = await getLatestWhatsAppVersion();
        
        const sock = makeWASocket({
            auth: state,
            connectTimeoutMs: 60000,
            maxRetries: 3,
            retryDelayMs: 2000,
            printQRInTerminal: true,
            ...(latestVersion ? { version: latestVersion } : {}),
            // Configuraciones adicionales para mantener la conexión estable
            keepAliveIntervalMs: 25000, // Enviar keep-alive cada 25 segundos
            // Configuración del navegador para evitar conflictos
            browser: [`ColombianGirls Bot ${sessionName}`, 'Chrome', '1.0.0'],
            // Configuración de sincronización
            syncFullHistory: false,
            // Configuración de mensajes
            markOnlineOnConnect: false,
            // Configuración de reconexión
            shouldIgnoreJid: jid => isJidBroadcast(jid),
            // Configuración de eventos
            emitOwnEvents: false,
            // Configuración de logging
            logger: pino({ level: 'silent' }),
            // Configuración de WebSocket
            ws: {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
        });

        // Asignar el socket a la variable global correspondiente
        if (sessionName === 'session1') {
            globalSocket1 = sock;
        } else {
            globalSocket2 = sock;
        }

        // Manejo de actualización de conexión
        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;
            console.log(`📡 Estado de conexión WhatsApp (${sessionName}):`, update);

            if (qr) {
                console.log(`🔄 Se generó un nuevo código QR para ${sessionName}`);
                console.log(`📱 Escanea este código QR con WhatsApp (${sessionName}):`);
                qrcode.generate(qr, { small: true });
                // Resetear estado cuando se genera QR
                if (sessionName === 'session1') {
                    isConnecting1 = false;
                } else {
                    isConnecting2 = false;
                }
            }

            if (connection === 'close') {
                // Resetear estado de conexión
                if (sessionName === 'session1') {
                    isConnecting1 = false;
                } else {
                    isConnecting2 = false;
                }
                
                const shouldReconnect = (lastDisconnect.error)?.output?.statusCode !== DisconnectReason.loggedOut;
                console.log(`❌ Conexión cerrada (${sessionName}):`, lastDisconnect.error, 'Reconectando:', shouldReconnect);
                
                // Email de caída con razón
                try {
                    const reason = formatDisconnectReason(lastDisconnect);
                    if (!waOutageActive || shouldEmailNow()) {
                        waOutageActive = true;
                        const ts = new Date().toISOString();
                        const stack = reason.stack ? String(reason.stack).slice(0, 4000) : '';
                        const html = `
                            <h3>🚨 WhatsApp Bot: Conexión caída</h3>
                            <p><b>Sesión:</b> ${sessionName}</p>
                            <p><b>Razón:</b> ${reason.label}</p>
                            <p><b>Mensaje:</b> ${reason.message || 'N/A'}</p>
                            <p><b>StatusCode:</b> ${typeof reason.statusCode === 'number' ? reason.statusCode : 'N/A'}</p>
                            <p><b>Fecha/Hora:</b> ${ts}</p>
                            ${stack ? `<details><summary>Stack</summary><pre>${stack}</pre></details>` : ''}
                        `;
                        sendAlertEmail('🚨 WhatsApp Bot: Conexión caída', html).catch(() => {});
                    }
                } catch (e) {
                    console.warn('⚠️ No se pudo generar correo de caída:', e?.message || e);
                }

                const currentReconnectAttempts = sessionName === 'session1' ? reconnectAttempts1 : reconnectAttempts2;
                
                if (shouldReconnect && currentReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                    if (sessionName === 'session1') {
                        reconnectAttempts1++;
                    } else {
                        reconnectAttempts2++;
                    }
                    
                    const attempts = sessionName === 'session1' ? reconnectAttempts1 : reconnectAttempts2;
                    console.log(`🔄 Intento de reconexión ${attempts}/${MAX_RECONNECT_ATTEMPTS} para ${sessionName}`);
                    
                    // Esperar antes de reconectar para evitar spam
                    setTimeout(() => {
                        connectToWhatsApp(sessionName, socketVariable, isConnectingVariable, reconnectAttemptsVariable);
                    }, 5000 * attempts); // Tiempo de espera progresivo
                } else if (currentReconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                    console.log(`❌ Máximo número de intentos de reconexión alcanzado para ${sessionName}`);
                    // Resetear contador después de un tiempo
                    setTimeout(() => {
                        if (sessionName === 'session1') {
                            reconnectAttempts1 = 0;
                        } else {
                            reconnectAttempts2 = 0;
                        }
                    }, 300000); // 5 minutos
                }
            } else if (connection === 'open') {
                console.log(`✅ Conexión WhatsApp establecida para ${sessionName}`);
                // Resetear estado de conexión
                if (sessionName === 'session1') {
                    isConnecting1 = false;
                    reconnectAttempts1 = 0;
                } else {
                    isConnecting2 = false;
                    reconnectAttempts2 = 0;
                }

                // Email de restauración
                try {
                    if (waOutageActive) {
                        waOutageActive = false;
                        const ts = new Date().toISOString();
                        const html = `
                            <h3>✅ WhatsApp Bot: Conexión restaurada</h3>
                            <p><b>Sesión:</b> ${sessionName}</p>
                            <p><b>Fecha/Hora:</b> ${ts}</p>
                            <p>La conexión al bot de WhatsApp se ha restaurado correctamente.</p>
                        `;
                        sendAlertEmail('✅ WhatsApp Bot: Conexión restaurada', html).catch(() => {});
                    }
                } catch (e) {
                    console.warn('⚠️ No se pudo generar correo de restauración:', e?.message || e);
                }
            }
        });

        // Guarda las credenciales cuando se actualicen
        sock.ev.on('creds.update', saveCreds);

        // Evento para recibir mensajes entrantes
        // Agregar al inicio del archivo, después de las importaciones
        const messageQueues = new Map();
        
        /**
         * Genera un tiempo de espera aleatorio entre 1 y 5 segundos
         * @returns {number} Tiempo en milisegundos
         */
        function getRandomDelayTime() {
            const minDelay = 0 * 1000; // 1 minuto
            const maxDelay = 0 * 60 * 1000; // 5 minutos
            return Math.floor(Math.random() * (maxDelay - minDelay + 1)) + minDelay;
        }
        
        /**
         * Calcula un retraso humano basado en la longitud del texto
         * para simular que una persona está escribiendo
         * @param {string} text - Texto a enviar
         * @returns {number} Milisegundos de espera
         */
        function calculateHumanDelayMs(text) {
            const baseMs = 800; // base ~0.8s
            const perCharMs = 30; // ~30ms por carácter
            const maxMs = 4000; // tope 4s
            const length = typeof text === 'string' ? text.length : 0;
            const calculated = baseMs + (length * perCharMs);
            return Math.min(maxMs, Math.max(baseMs, calculated));
        }

        /**
         * Envía un mensaje de texto simulando presencia/tipeo humano de forma secuencial (sincrónica)
         * @param {any} sock - Socket de Baileys
         * @param {string} remoteJid - JID destino
         * @param {string} text - Texto a enviar
         */
        async function simulateHumanReply(sock, remoteJid, text) {
            const delayMs = calculateHumanDelayMs(text);
            try { await sock.presenceSubscribe(remoteJid); } catch {}
            try { await sock.sendPresenceUpdate('composing', remoteJid); } catch {}
            await new Promise(resolve => setTimeout(resolve, delayMs));
            await sock.sendMessage(remoteJid, { text });
            try { await sock.sendPresenceUpdate('paused', remoteJid); } catch {}
        }
    
        // Modificar el evento de mensajes
        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            console.log(`📨 Mensaje recibido (${sessionName}):`, type, messages.length);
        
            for (const message of messages) {
                if (!message.message) continue;
                if (message.key.fromMe) continue;
        
                const remoteJid = message.key.remoteJid;
                const phoneDigits = remoteJid.split('@')[0];
                const isImage = !!message.message.imageMessage;
                const isText = !!(message.message.conversation || message.message.extendedTextMessage?.text);
                const isVideo = !!message.message.videoMessage;
                const isAudio = !!message.message.audioMessage;
                let contentToSend = message.message.conversation || 
                                 message.message.extendedTextMessage?.text || 
                                 message.message.imageMessage?.caption ||
                                    '';
                let typeToSend = 'text';
                let imageBase64 = null;
                let audioBase64 = null;
                if (isImage) {
                    typeToSend = 'image';
                    // El content debe ir vacío si es imagen
                    contentToSend = '';
                    // Descargar la imagen y convertir a base64
                    try {
                        const buffer = await downloadMediaMessage(
                            message,
                            'buffer',
                            {},
                            {
                                reuploadRequest: sock.updateMediaMessage
                            }
                        );
                        imageBase64 = buffer.toString('base64');
                        console.log(`📸 Imagen descargada (${sessionName}): ${(buffer.length / 1024 / 1024).toFixed(2)} MB`);
                    } catch (err) {
                        console.error(`Error al descargar imagen (${sessionName}):`, err);
                    }
                } else if (isVideo) {
                    typeToSend = 'video';
                    contentToSend = '';
                    imageBase64 = null;
                } else if (isAudio) {
                    typeToSend = 'audio';
                    contentToSend = '';
                    imageBase64 = null;
                    // Descargar el audio y convertir a base64
                    try {
                        const buffer = await downloadMediaMessage(
                            message,
                            'buffer',
                            {},
                            {
                                reuploadRequest: sock.updateMediaMessage
                            }
                        );
                        audioBase64 = buffer.toString('base64');
                        console.log(`🎵 Audio descargado (${sessionName}): ${(buffer.length / 1024 / 1024).toFixed(2)} MB`);
                    } catch (err) {
                        console.error(`Error al descargar audio (${sessionName}):`, err);
                    }
                }
        
                const newMessage = {
                    from: remoteJid,
                    sender: message.pushName || remoteJid.split('@')[0],
                    message: contentToSend,
                    timestamp: (message.messageTimestamp * 1000) || Date.now(),
                    type: typeToSend,
                    image_base64: imageBase64,
                    audio_base64: audioBase64,
                    session: sessionName // Agregar información de la sesión
                };
                // Asociar número -> sesión que recibió el mensaje
                if (phoneDigits) {
                    phoneSessionMap.set(phoneDigits, sessionName);
                }
        
                // Agregar mensaje a la cola del usuario
                if (!messageQueues.has(remoteJid)) {
                    messageQueues.set(remoteJid, {
                        messages: [],
                        timeoutId: null
                    });
                }
        
                const userQueue = messageQueues.get(remoteJid);
                userQueue.messages.push(newMessage);
        
                // Limpiar el timeout anterior si existe
                if (userQueue.timeoutId) {
                    clearTimeout(userQueue.timeoutId);
                }
        
                // Establecer nuevo timeout con tiempo aleatorio
                const randomDelay = getRandomDelayTime();
                console.log(`⏰ Tiempo de espera aleatorio configurado (${sessionName}): ${randomDelay/1000} segundos`);
                userQueue.timeoutId = setTimeout(async () => {
                    try {
                        const messages = userQueue.messages;
                        messageQueues.delete(remoteJid); // Limpiar la cola
        
                        // Combinar todos los mensajes en un solo contenido
                        const combinedQuery = messages.map(m => m.message).join('\n');
                        
                        // Obtener todas las imágenes en base64
                        const imagesBase64 = messages.map(m => m.image_base64).filter(Boolean);
                        
                        // Obtener todos los audios en base64
                        const audiosBase64 = messages.map(m => m.audio_base64).filter(Boolean);
                        
                        // Verificar todos los tipos de mensajes presentes (DEBE IR ANTES DE SU USO)
                        const hasVideo = messages.some(m => m.type === 'video');
                        const hasAudio = messages.some(m => m.type === 'audio');
                        const hasImage = messages.some(m => m.type === 'image');
                        
                        // Determinar el contenido apropiado según el tipo
                        let finalContent = combinedQuery;
                        if (hasVideo) {
                            finalContent = ''; // Los videos no tienen contenido de texto
                        } else if (hasAudio) {
                            finalContent = combinedQuery || ''; // Mantener texto si existe
                        } else if (hasImage) {
                            finalContent = combinedQuery || ''; // Mantener caption si existe
                        }
                        
                        // Log informativo sobre archivos multimedia
                        if (imagesBase64.length > 0) {
                            const totalImageSize = imagesBase64.reduce((total, img) => total + (img.length * 0.75), 0);
                            console.log(`📸 Procesando ${imagesBase64.length} imagen(es) (${sessionName}) - Tamaño total: ${(totalImageSize / 1024 / 1024).toFixed(2)} MB`);
                        }
                        
                        if (audiosBase64.length > 0) {
                            const totalAudioSize = audiosBase64.reduce((total, audio) => total + (audio.length * 0.75), 0);
                            console.log(`🎵 Procesando ${audiosBase64.length} audio(s) (${sessionName}) - Tamaño total: ${(totalAudioSize / 1024 / 1024).toFixed(2)} MB`);
                        }
                        
                        /**
                         * Determinar el tipo final con prioridad:
                         * 1. Video (mayor prioridad) - para mensajes de video
                         * 2. Audio - para mensajes de audio/notas de voz
                         * 3. Image - para mensajes con imágenes
                         * 4. Text (menor prioridad) - para mensajes de texto puro
                         */
                        let finalType = 'text';
                        if (hasVideo) {
                            finalType = 'video';
                        } else if (hasAudio) {
                            finalType = 'audio';
                        } else if (hasImage) {
                            finalType = 'image';
                        }
                        
                        // Crear el payload estándar con tipo correcto
                        const payload = {
                            messages: [
                                {
                                    role: "user",
                                    content: finalContent,
                                    type: finalType,
                                    image_base64: hasVideo || hasAudio ? undefined : (imagesBase64.length > 0 ? imagesBase64 : undefined),
                                    audio_base64: hasVideo ? undefined : (audiosBase64.length > 0 ? audiosBase64 : undefined)
                                }
                            ]
                        };
                        
                        // Crear payload unificado con estructura estándar para todos los tipos
                        const unifiedPayload = {
                            messages: [
                                {
                                    role: "user",
                                    content: finalContent,
                                    type: finalType,
                                    image_base64: hasImage ? imagesBase64 : undefined,
                                    audio_base64: hasAudio ? audiosBase64 : undefined
                                }
                            ]
                        };
                        
                        // Payloads eliminados - ahora se usa unifiedPayload para todos los tipos
                        
                        // Crear payload para logging sin contenido base64
                        const logPayload = {
                            messages: [
                                {
                                    role: "user",
                                    content: finalContent,
                                    type: finalType,
                                    image_base64: hasVideo || hasAudio ? undefined : (imagesBase64.length > 0 ? `[${imagesBase64.length} imagen(es) en base64]` : undefined),
                                    audio_base64: hasVideo ? undefined : (audiosBase64.length > 0 ? `[${audiosBase64.length} audio(s) en base64]` : undefined)
                                }
                            ]
                        };
                        
                        // Verificar que la URL esté configurada
                        const apiUrl = process.env.URL_N8N || 'http://localhost:8000/api/v1/chat';
                        console.log(`🌐 Intentando conectar a: ${apiUrl} (${sessionName})`);
                        
                        // Usar el payload unificado para todos los tipos de contenido
                        let requestPayload = unifiedPayload;
                        console.log(`📦 Usando payload unificado para ${finalType} (${sessionName})`);
                        
                        // Log informativo sobre el tipo de mensaje detectado
                        console.log(`📋 Tipo de mensaje detectado (${sessionName}): ${finalType}`);
                        console.log(`📊 Resumen de tipos (${sessionName}): Video=${hasVideo}, Audio=${hasAudio}, Image=${hasImage}, Text=${!hasVideo && !hasAudio && !hasImage}`);
                        console.log(`➡️ Payload enviado a la API agent/chat/message (formato estándar) (${sessionName}):`, JSON.stringify(logPayload, null, 2));
                        
                        // Log del payload real que se envía
                        console.log(`📦 Payload real enviado (${sessionName}):`, JSON.stringify({
                            messages: [
                                {
                                    role: requestPayload.messages[0].role,
                                    content: requestPayload.messages[0].content,
                                    type: requestPayload.messages[0].type,
                                    image_base64: requestPayload.messages[0].image_base64 ? `[${requestPayload.messages[0].image_base64.length} imagen(es) en base64]` : 'null',
                                    audio_base64: requestPayload.messages[0].audio_base64 ? `[${requestPayload.messages[0].audio_base64.length} audio(s) en base64]` : 'null'
                                }
                            ]
                        }, null, 2));
                        
                        const response = await axios.post(apiUrl, requestPayload, {
                            params: {
                                phone: remoteJid.split('@')[0],
                                session: sessionName, // Agregar parámetro de sesión
                                // Enviar también el puerto en uso del servicio actual
                                port: PORT
                            },
                            timeout: 30000, // 30 segundos de timeout
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        });

                        
                        console.log(`✅ Respuesta de API agent/chat/message (${sessionName}):`, JSON.stringify(response.data, null, 2));
                        // Éxito del webhook: opcionalmente limpiar estado de caída del webhook
                        webhookOutageActive = false;
                        
                        // Extraer el texto de respuesta de la API con lógica mejorada
                        let replyText = '';
                        
                        if (response.data) {
                            // Intentar diferentes estructuras de respuesta de forma más exhaustiva
                            if (response.data.data && response.data.data.content) {
                                replyText = response.data.data.content;
                            } else if (response.data.data && response.data.data.message) {
                                replyText = response.data.data.message;
                            } else if (response.data.data && typeof response.data.data === 'string') {
                                replyText = response.data.data;
                            } else if (response.data.content) {
                                replyText = response.data.content;
                            } else if (response.data.message) {
                                replyText = response.data.message;
                            } else if (response.data.text) {
                                replyText = response.data.text;
                            } else if (response.data.response) {
                                replyText = response.data.response;
                            } else if (typeof response.data === 'string') {
                                replyText = response.data;
                            } else if (response.data.result && response.data.result.content) {
                                replyText = response.data.result.content;
                            } else if (response.data.result && response.data.result.message) {
                                replyText = response.data.result.message;
                            } else if (response.data.result && typeof response.data.result === 'string') {
                                replyText = response.data.result;
                            }
                            
                            // Log para debugging
                            console.log(`🔍 Contenido extraído (${sessionName}):`, replyText ? `"${replyText.substring(0, 100)}..."` : 'NULO');
                        }
                        
                        // Verificar si se envió contenido multimedia (video, audio, imagen)
                        const hasMultimedia = hasVideo || hasAudio || hasImage;
                        
                        // Solo enviar texto si hay contenido válido
                        if (replyText && replyText.trim()) {
                            // Limpiar formato de markdown si es necesario
                            replyText = replyText.replace(/\*\*/g, '*');
                            
                            // Enviar la respuesta simulando tipeo humano de forma sincrónica
                            await simulateHumanReply(sock, remoteJid, replyText);
                            console.log(`📤 Respuesta enviada a ${remoteJid} (${sessionName}): ${replyText.substring(0, 50)}...`);
                        } else if (hasMultimedia) {
                            // Si se envió multimedia y no hay respuesta de texto, no enviar nada adicional
                            if (!replyText || replyText.trim() === '') {
                                console.log(`✅ Multimedia enviada exitosamente - API respondió con string vacío (${sessionName})`);
                                console.log(`📊 Resumen: ${hasVideo ? 'Video' : ''}${hasAudio ? 'Audio' : ''}${hasImage ? 'Imagen' : ''} enviado, no se requiere respuesta adicional`);
                            } else {
                                // Solo enviar confirmación si la API respondió con texto que no es válido
                                let confirmationMessage = '';
                                if (hasVideo) {
                                    confirmationMessage = '✅ Video enviado correctamente';
                                } else if (hasAudio) {
                                    confirmationMessage = '✅ Audio enviado correctamente';
                                } else if (hasImage) {
                                    confirmationMessage = '✅ Imagen enviada correctamente';
                                }
                                
                                if (confirmationMessage) {
                                    await simulateHumanReply(sock, remoteJid, confirmationMessage);
                                    console.log(`📤 Confirmación enviada a ${remoteJid} (${sessionName}): ${confirmationMessage}`);
                                }
                            }
                        } else if (!replyText || replyText.trim() === '') {
                            // Si la API responde con string vacío, no hacer nada y no mostrar error
                            console.log(`ℹ️ API respondió con string vacío (${sessionName}) - No se requiere acción adicional`);
                        } else {
                            // Solo mostrar warning si hay contenido pero no es válido
                            console.log(`⚠️ No se encontró contenido válido en la respuesta para enviar (${sessionName})`);
                            console.log(`📋 Estructura completa de la respuesta (${sessionName}):`, JSON.stringify(response.data, null, 2));
                        }
                    } catch (error) {
                        console.error(`❌ Error al procesar mensajes agrupados (${sessionName}):`, error.message);
                        
                        // Log detallado del error
                        if (error.response) {
                            console.error(`📊 Detalles del error HTTP (${sessionName}):`);
                            console.error('   Status:', error.response.status);
                            console.error('   Status Text:', error.response.statusText);
                            console.error('   Headers:', error.response.headers);
                            console.error('   Data:', error.response.data);
                        } else if (error.request) {
                            console.error(`🌐 Error de red - No se recibió respuesta del servidor (${sessionName})`);
                            console.error('   Request:', error.request);
                        } else {
                            console.error(`🔧 Error de configuración (${sessionName}):`, error.message);
                        }
                        
                        // Email de error de webhook
                        try {
                            const targetUrl = process.env.URL_N8N || 'http://localhost:8000/api/v1/chat';
                            if (!webhookOutageActive || shouldEmailNow()) {
                                webhookOutageActive = true;
                                const ts = new Date().toISOString();
                                const stack = error?.stack ? String(error.stack).slice(0, 4000) : '';
                                const html = `
                                    <h3>🚨 WhatsApp Bot: Error llamando al webhook</h3>
                                    <p><b>Sesión:</b> ${sessionName}</p>
                                    <p><b>URL:</b> ${targetUrl}</n>
                                    <p><b>Mensaje:</b> ${error?.message || 'N/A'}</p>
                                    <p><b>Fecha/Hora:</b> ${ts}</p>
                                    ${stack ? `<details><summary>Stack</summary><pre>${stack}</pre></details>` : ''}
                                `;
                                sendAlertEmail('🚨 WhatsApp Bot: Error llamando al webhook', html).catch(() => {});
                            }
                        } catch (e) {
                            console.warn('⚠️ No se pudo generar correo de error de webhook:', e?.message || e);
                        }

                        // Verificar si el backend está disponible
                        const apiUrl = process.env.URL_N8N || 'http://localhost:8000/api/v1/chat';
                        console.log(`🔍 Verificando conectividad con: ${apiUrl} (${sessionName})`);
                        
                        try {
                            const healthCheck = await axios.get(apiUrl.replace('/api/v1/chat', '/health'), { timeout: 5000 });
                            console.log(`✅ Backend está disponible (${sessionName})`);
                        } catch (healthError) {
                            console.error(`❌ Backend no está disponible (${sessionName}):`, healthError.message);
                        }
                    }
                }, randomDelay);
        
                newMessages.push(newMessage);
            }
        });
    } catch (error) {
        console.error(`❌ Error al iniciar la conexión a WhatsApp (${sessionName}):`, error.message);
        // Resetear estado de conexión
        if (sessionName === 'session1') {
            isConnecting1 = false;
            reconnectAttempts1 = 0;
        } else {
            isConnecting2 = false;
            reconnectAttempts2 = 0;
        }
        setTimeout(() => {
            connectToWhatsApp(sessionName, socketVariable, isConnectingVariable, reconnectAttemptsVariable);
        }, 30000); // Esperar 30 segundos antes de intentar reconectar
    }
}

/**
 * Función para obtener el socket activo basado en el número de teléfono
 * @param {string} phone - Número de teléfono
 * @returns {Object|null} Socket activo o null si no hay conexión
 */
function getActiveSocket(phone) {
    // Aquí puedes implementar lógica para determinar qué sesión usar
    // Por ahora, usaremos session1 como predeterminada
    // En el futuro, puedes agregar lógica para distribuir entre sesiones
    return globalSocket1;
}

/**
 * Endpoint para enviar mensaje de texto vía WhatsApp
 */
app.post('/api/send-message', async (req, res) => {
    try {
        const { number, message, session } = req.body;
        if (!number || !message) {
            return res.status(400).json({ success: false, error: 'Faltan datos: number o message' });
        }
        const phoneDigits = String(number || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        if (!activeSocket) {
            return res.status(500).json({ success: false, error: 'WhatsApp no está conectado' });
        }
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`📱 Enviando mensaje a ${formattedNumber}`);

        try {
            await Promise.race([
                activeSocket.sendMessage(formattedNumber, { text: message }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar mensaje')), 25000))
            ]);
            return res.json({ success: true, message: 'Mensaje enviado correctamente' });
        } catch (error) {
            return res.status(500).json({ success: false, error: error.message || 'Error al enviar mensaje' });
        }
    } catch (error) {
        return res.status(500).json({ success: false, error: error.message || 'Error general' });
    }
});

/**
 * Envía una imagen recibida en formato hexadecimal al número proporcionado
 * @param {Object} req - Objeto de solicitud HTTP
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-images', async (req, res) => {
    try {
        /**
         * Recibe un número de teléfono, una imagen en base64 y un caption opcional para enviar una imagen por WhatsApp.
         * @param {string} phone - Número de teléfono del destinatario.
         * @param {string} imageBase64 - Imagen codificada en base64.
         * @param {string} [caption] - Texto opcional que acompaña la imagen.
         */
        const { phone, imageBase64, caption = '', session } = req.body;
        
        if (!phone || !imageBase64) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la imagen en formato base64 son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);

        if (!activeSocket) {
            return res.status(500).json({ 
                status: false, 
                message: 'WhatsApp no está conectado' 
            });
        }

        // Convertir la imagen de base64 a buffer
        const imageBuffer = Buffer.from(imageBase64, 'base64');
        
        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        
        // Enviar la imagen con el caption
        const result = await activeSocket.sendMessage(formattedNumber, {
            image: imageBuffer,
            caption: caption
        });
        
        res.status(200).json({
            status: true,
            message: 'Imagen enviada correctamente',
            data: {
                result: result
            }
        });
    } catch (error) {
        console.error('Error al enviar imagen:', error);
        res.status(500).json({
            status: false,
            message: 'Error al enviar imagen',
            error: error.message
        });
    }
});

/**
 * Función auxiliar para procesar URLs de imágenes problemáticas
 * @param {string} url - URL de la imagen a procesar
 * @returns {string} URL procesada
 */
function processImageUrl(url) {
    // Manejar URLs de Google Drive
    if (url.includes('drive.google.com')) {
        const driveIdMatch = url.match(/\/d\/([a-zA-Z0-9-_]+)/);
        if (driveIdMatch) {
            const fileId = driveIdMatch[1];
            return `https://drive.google.com/uc?export=download&id=${fileId}`;
        }
    }
    
    // Manejar URLs de Dropbox
    if (url.includes('dropbox.com')) {
        // Convertir URLs de Dropbox a formato de descarga directa
        if (url.includes('?dl=0')) {
            return url.replace('?dl=0', '?dl=1');
        } else if (!url.includes('?dl=')) {
            return url + '?dl=1';
        }
    }
    
    // Manejar URLs de OneDrive
    if (url.includes('1drv.ms') || url.includes('onedrive.live.com')) {
        // Para OneDrive, intentar obtener el enlace directo
        return url.replace('/redir?', '/download?');
    }
    
    return url;
}

/**
 * Envía una imagen desde una URL pública al número proporcionado
 * @param {Object} req - Objeto de solicitud HTTP con phone, imageUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-image-url', async (req, res) => {
    try {
        const { phone, imageUrl, caption = '', session } = req.body;

        if (!phone || !imageUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL de la imagen son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        
        if (!activeSocket) {
            return res.status(500).json({ 
                status: false, 
                message: 'WhatsApp no está conectado' 
            });
        }

        // Formatear el número de teléfono (usar el mismo formato que el endpoint de mensajes de texto)
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`📸 Enviando imagen desde URL a ${formattedNumber}`);

        try {
            // Validar que la URL de la imagen no esté vacía
            if (!imageUrl || typeof imageUrl !== 'string' || imageUrl.trim() === '') {
                throw new Error('La URL de la imagen es inválida o está vacía');
            }
            
            // Procesar la URL para manejar casos especiales
            let processedImageUrl = processImageUrl(imageUrl);
            if (processedImageUrl !== imageUrl) {
                console.log(`🔄 URL procesada: ${imageUrl} -> ${processedImageUrl}`);
            }
            
            // Verificar si la URL es válida antes de enviarla
            if (processedImageUrl.startsWith('http')) {
                try {
                    console.log(`🔍 Verificando URL de imagen: ${processedImageUrl}`);
                    
                    // Intentar obtener información de la imagen con GET en lugar de HEAD
                    // para manejar mejor las redirecciones y URLs que no soportan HEAD
                    const response = await Promise.race([
                        axios.get(processedImageUrl, {
                            responseType: 'arraybuffer',
                            timeout: 15000,
                            maxRedirects: 5,
                            validateStatus: function (status) {
                                return status >= 200 && status < 300; // Solo aceptar códigos 2xx
                            }
                        }),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Timeout al verificar la imagen')), 15000)
                        )
                    ]);
                    
                    // Verificar si la respuesta contiene un tipo de contenido de imagen
                    const contentType = response.headers['content-type'];
                    console.log(`📊 Content-Type recibido: ${contentType}`);
                    
                    if (!contentType || !contentType.startsWith('image/')) {
                        // Log adicional para debugging
                        console.error(`❌ URL no devuelve imagen válida:`);
                        console.error(`   URL: ${imageUrl}`);
                        console.error(`   Content-Type: ${contentType}`);
                        console.error(`   Status: ${response.status}`);
                        console.error(`   Headers:`, response.headers);
                        
                        // Si es HTML, probablemente es una página de error o login
                        if (contentType && contentType.includes('text/html')) {
                            throw new Error(`La URL devuelve HTML en lugar de imagen. Posible página de login o error. Content-Type: ${contentType}`);
                        }
                        
                        throw new Error(`El recurso no es una imagen válida: ${contentType}`);
                    }
                    
                    console.log(`✅ Imagen válida: ${contentType} (${(response.data.length / 1024).toFixed(2)} KB)`);
                    
                } catch (urlError) {
                    console.error('❌ Error al verificar la URL de la imagen:', urlError.message);
                    
                    // Log detallado del error
                    if (urlError.response) {
                        console.error('   Status:', urlError.response.status);
                        console.error('   Status Text:', urlError.response.statusText);
                        console.error('   Headers:', urlError.response.headers);
                    }
                    
                    throw new Error(`URL de imagen inválida o inaccesible: ${urlError.message}`);
                }
            } else if (!fs.existsSync(imageUrl)) {
                // Si es una ruta local, verificar que el archivo exista
                throw new Error(`El archivo de imagen no existe en la ruta: ${imageUrl}`);
            }

            // Enviar la imagen con caption usando el formato que funciona: { url: processedImageUrl }
            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, {
                    image: { url: processedImageUrl }
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar imagen')), 25000))
            ]);

            console.log('✅ Resultado del envío:', result);

            res.status(200).json({
                status: true,
                message: 'Imagen enviada correctamente desde URL',
                data: {
                    phone: formattedNumber,
                    originalUrl: imageUrl,
                    processedUrl: processedImageUrl,
                    caption: caption
                }
            });

        } catch (downloadError) {
            console.error('Error al descargar imagen:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al descargar la imagen desde la URL proporcionada',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al enviar imagen desde URL:', error);
        res.status(500).json({
            status: false,
            message: 'Error al enviar imagen desde URL',
            error: error.message
        });
    }
});

/**
 * Envía un video desde una URL pública al número proporcionado
 * @param {Object} req - Objeto de solicitud HTTP con phone, videoUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-video-url', async (req, res) => {
    try {
        const { phone, videoUrl, caption = '', session } = req.body;

        if (!phone || !videoUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL del video son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);

        if (!activeSocket) {
            return res.status(500).json({ 
                status: false, 
                message: 'WhatsApp no está conectado' 
            });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`🎥 Enviando video desde URL a ${formattedNumber}`);

        try {
            // Validar que la URL del video no esté vacía
            if (!videoUrl || typeof videoUrl !== 'string' || videoUrl.trim() === '') {
                throw new Error('La URL del video es inválida o está vacía');
            }
            
            // Verificar si la URL es válida antes de enviarla
            let finalVideoUrl = videoUrl; // Variable para almacenar la URL final
            
            if (videoUrl.startsWith('http')) {
                try {
                    // Manejo especial para URLs de Google Drive
                    if (videoUrl.includes('drive.google.com')) {
                        // Extraer el ID del archivo de Google Drive
                        const driveIdMatch = videoUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
                        if (driveIdMatch) {
                            const fileId = driveIdMatch[1];
                            // Crear enlace de descarga directa
                            finalVideoUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
                            console.log(`🔄 URL de Google Drive convertida: ${finalVideoUrl}`);
                        } else {
                            throw new Error('No se pudo extraer el ID del archivo de Google Drive');
                        }
                    }
                    
                    // Verificar si el video existe y es accesible
                    const response = await Promise.race([
                        axios.head(finalVideoUrl),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Timeout al verificar el video')), 10000)
                        )
                    ]);
                    
                    // Verificar si la respuesta contiene un tipo de contenido de video
                    const contentType = response.headers['content-type'];
                    if (!contentType || !contentType.startsWith('video/')) {
                        throw new Error(`El recurso no es un video válido: ${contentType}`);
                    }
                    console.log(`📊 Video válido: ${contentType}`);
                } catch (urlError) {
                    console.error('Error al verificar la URL del video:', urlError.message);
                    throw new Error(`URL de video inválida o inaccesible: ${urlError.message}`);
                }
            } else if (!fs.existsSync(videoUrl)) {
                // Si es una ruta local, verificar que el archivo exista
                throw new Error(`El archivo de video no existe en la ruta: ${videoUrl}`);
            }

            // Enviar el video sin caption usando el formato que funciona: { url: finalVideoUrl }
            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, {
                    video: { url: finalVideoUrl }
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar video')), 30000))
            ]);

            console.log('✅ Resultado del envío de video:', result);

            res.status(200).json({
                status: true,
                message: 'Video enviado correctamente desde URL',
                data: {
                    phone: formattedNumber,
                    videoUrl: finalVideoUrl,
                    originalUrl: videoUrl
                }
            });

        } catch (downloadError) {
            console.error('Error al descargar video:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al descargar el video desde la URL proporcionada',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al enviar video desde URL:', error);
        res.status(500).json({
            status: false,
            message: 'Error al enviar video desde URL',
            error: error.message
        });
    }
});

/**
 * Envía un audio desde una URL pública al número proporcionado
 * @param {Object} req - Objeto de solicitud HTTP con phone, audioUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-audio-url', async (req, res) => {
    try {
        /**
         * Recibe un número de teléfono, una imagen en base64 y un caption opcional para enviar una imagen por WhatsApp.
         * @param {string} phone - Número de teléfono del destinatario.
         * @param {string} imageBase64 - Imagen codificada en base64.
         * @param {string} [caption] - Texto opcional que acompaña la imagen.
         */
        const { phone, audioUrl, caption = '', session } = req.body;
        const forceVoiceNote = Boolean(req.body.asVoiceNote || req.body.forceVoiceNote);
        
        if (!phone || !audioUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL del audio son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);

        if (!activeSocket) {
            return res.status(500).json({ 
                status: false, 
                message: 'WhatsApp no está conectado' 
            });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`🎵 Enviando audio desde URL a ${formattedNumber}`);
        console.log(`🔗 URL del audio: ${audioUrl}`);

        try {
            // Validar que la URL del audio no esté vacía
            if (!audioUrl || typeof audioUrl !== 'string' || audioUrl.trim() === '') {
                throw new Error('La URL del audio es inválida o está vacía');
            }
            
            // Verificar si la URL es válida antes de enviarla
            let finalAudioUrl = audioUrl; // Variable para almacenar la URL final
            // Mimetype detectado por verificación remota (si aplica)
            let resolvedContentType = null;
            let isOpusVoice = false; // true si es OGG Opus (nota de voz)
            
            if (audioUrl.startsWith('http')) {
                try {
                    // Manejo especial para URLs de Google Drive
                    if (audioUrl.includes('drive.google.com')) {
                        // Extraer el ID del archivo de Google Drive
                        const driveIdMatch = audioUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
                        if (driveIdMatch) {
                            const fileId = driveIdMatch[1];
                            // Crear enlace de descarga directa
                            finalAudioUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
                            console.log(`🔄 URL de Google Drive convertida: ${finalAudioUrl}`);
                        } else {
                            throw new Error('No se pudo extraer el ID del archivo de Google Drive');
                        }
                    }
                    
                    // Verificar si el audio existe y es accesible
                    const response = await Promise.race([
                        axios.head(finalAudioUrl),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Timeout al verificar el audio')), 10000)
                        )
                    ]);
                    
                    // Verificar si la respuesta contiene un tipo de contenido de audio
                    const contentType = response.headers['content-type'];
                    resolvedContentType = contentType || null;
                    if (!contentType || !contentType.startsWith('audio/')) {
                        throw new Error(`El recurso no es un audio válido: ${contentType}`);
                    }
                    // Determinar si es OGG Opus (nota de voz)
                    isOpusVoice = /audio\/ogg/.test(contentType) || /opus/i.test(contentType);
                    console.log(`📊 Audio válido: ${contentType} (voiceNote=${isOpusVoice})`);
                } catch (urlError) {
                    console.error('Error al verificar la URL del audio:', urlError.message);
                    throw new Error(`URL de audio inválida o inaccesible: ${urlError.message}`);
                }
            } else if (!fs.existsSync(audioUrl)) {
                // Si es una ruta local, verificar que el archivo exista
                throw new Error(`El archivo de audio no existe en la ruta: ${audioUrl}`);
            }

            // Construcción del mensaje según el tipo detectado o forzado
            /**
             * Si se fuerza nota de voz o el archivo ya es OGG Opus, enviar con ptt: true.
             * En caso de MP3 y forceVoiceNote, se transcodifica a OGG Opus.
             */
            let audioMessage;
            if (forceVoiceNote) {
                let oggBuffer = null;
                if (isOpusVoice && finalAudioUrl.startsWith('http')) {
                    audioMessage = {
                        audio: { url: finalAudioUrl },
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true,
                        fileName: `voice_message_${Date.now()}.ogg`
                    };
                } else {
                    // Descargar y convertir a OGG Opus
                    let sourceBuffer = null;
                    if (finalAudioUrl.startsWith('http')) {
                        const getResp = await axios.get(finalAudioUrl, { responseType: 'arraybuffer', timeout: 30000 });
                        sourceBuffer = Buffer.from(getResp.data);
                    } else {
                        sourceBuffer = await fs.promises.readFile(finalAudioUrl);
                    }
                    oggBuffer = await transcodeBufferToOggOpus(sourceBuffer);
                    audioMessage = {
                        audio: oggBuffer,
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true,
                        fileName: `voice_message_${Date.now()}.ogg`
                    };
                }
            } else {
                const isVoiceNote = Boolean(isOpusVoice);
                audioMessage = isVoiceNote
                    ? {
                        audio: { url: finalAudioUrl },
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true,
                        fileName: `voice_message_${Date.now()}.ogg`
                    }
                    : {
                        audio: { url: finalAudioUrl },
                        mimetype: resolvedContentType || 'audio/mpeg',
                        ptt: false,
                        fileName: `audio_${Date.now()}.mp3`
                    };
            }
            
            // Agregar caption solo cuando NO es nota de voz
            if (!audioMessage.ptt && caption && caption.trim()) {
                audioMessage.caption = caption.trim();
            }

            // Log del mensaje que se va a enviar
            console.log(`📤 Enviando mensaje de audio:`, JSON.stringify(audioMessage, null, 2));

            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, audioMessage),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar audio')), 25000))
            ]);

            console.log('✅ Resultado del envío de audio:', result);

            res.status(200).json({
                status: true,
                message: 'Audio enviado correctamente desde URL',
                data: {
                    phone: formattedNumber,
                    audioUrl: finalAudioUrl,
                    originalUrl: audioUrl
                }
            });
        } catch (downloadError) {
            console.error('Error al descargar audio:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al descargar el audio desde la URL proporcionada',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al enviar audio desde URL:', error);
        res.status(500).json({
            status: false,
            message: 'Error al enviar audio desde URL',
            error: error.message
        });
    }
});

/**
 * Envía un audio descargándolo primero desde una URL (útil para Google Drive)
 * @param {Object} req - Objeto de solicitud HTTP con phone, audioUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-audio-download', async (req, res) => {
    try {
        const { phone, audioUrl, caption = '', session } = req.body;

        if (!phone || !audioUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL del audio son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);

        if (!activeSocket) {
            return res.status(500).json({ 
                status: false, 
                message: 'WhatsApp no está conectado' 
            });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`🎵 Descargando y enviando audio desde URL a ${formattedNumber}`);
        console.log(`🔗 URL del audio: ${audioUrl}`);

        try {
            // Validar que la URL del audio no esté vacía
            if (!audioUrl || typeof audioUrl !== 'string' || audioUrl.trim() === '') {
                throw new Error('La URL del audio es inválida o está vacía');
            }
            
            // Procesar URL de Google Drive si es necesario
            let processedUrl = audioUrl;
            if (audioUrl.includes('drive.google.com')) {
                console.log(`🔍 Detectada URL de Google Drive: ${audioUrl}`);
                const driveIdMatch = audioUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
                if (driveIdMatch) {
                    const fileId = driveIdMatch[1];
                    processedUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
                    console.log(`🔄 URL de Google Drive convertida: ${processedUrl}`);
                } else {
                    console.log(`⚠️ URL de Google Drive detectada pero formato no reconocido: ${audioUrl}`);
                    console.log(`ℹ️ Continuando con la URL original...`);
                    // No lanzar error, continuar con la URL original
                }
            } else {
                console.log(`🔗 URL normal detectada: ${audioUrl}`);
            }

            // Descargar el audio
            console.log('📥 Descargando audio...');
            const audioResponse = await Promise.race([
                axios.get(processedUrl, {
                    responseType: 'arraybuffer',
                    timeout: 30000, // 30 segundos para descarga
                    maxContentLength: 50 * 1024 * 1024 // Máximo 50MB
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Timeout al descargar el audio')), 30000)
                )
            ]);

            const audioBuffer = Buffer.from(audioResponse.data);
            console.log(`📊 Audio descargado: ${(audioBuffer.length / 1024 / 1024).toFixed(2)} MB`);

            // Verificar el tipo de contenido
            const contentType = audioResponse.headers['content-type'];
            if (!contentType || !contentType.startsWith('audio/')) {
                throw new Error(`El recurso no es un audio válido: ${contentType}`);
            }

            // Enviar el audio como buffer
            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, {
                    audio: audioBuffer,
                    mimetype: contentType,
                    ptt: false // ptt: false para audio normal, true para mensaje de voz
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar audio')), 25000))
            ]);

            console.log('✅ Audio enviado correctamente como buffer');

            res.status(200).json({
                status: true,
                message: 'Audio descargado y enviado correctamente',
                data: {
                    phone: formattedNumber,
                    audioUrl: audioUrl,
                    size: `${(audioBuffer.length / 1024 / 1024).toFixed(2)} MB`,
                    contentType: contentType
                }
            });

        } catch (downloadError) {
            console.error('Error al descargar o enviar audio:', downloadError);
            
            // Determinar el tipo de error para dar mejor respuesta
            let errorMessage = 'Error al descargar o enviar el audio';
            let errorDetails = downloadError.message;
            
            if (downloadError.code === 'ECONNREFUSED') {
                errorMessage = 'No se pudo conectar al servidor del audio';
            } else if (downloadError.code === 'ENOTFOUND') {
                errorMessage = 'URL del audio no encontrada o inaccesible';
            } else if (downloadError.code === 'ETIMEDOUT') {
                errorMessage = 'Tiempo de espera agotado al descargar el audio';
            } else if (downloadError.response?.status === 404) {
                errorMessage = 'Archivo de audio no encontrado (404)';
            } else if (downloadError.response?.status === 403) {
                errorMessage = 'Acceso denegado al archivo de audio (403)';
            }
            
            return res.status(400).json({
                status: false,
                message: errorMessage,
                error: errorDetails,
                url: audioUrl
            });
        }

    } catch (error) {
        console.error('Error al procesar audio:', error);
        res.status(500).json({
            status: false,
            message: 'Error al procesar audio',
            error: error.message
        });
    }
});

/**
 * Envía un video descargándolo primero desde una URL (útil para Google Drive)
 * @param {Object} req - Objeto de solicitud HTTP con phone, videoUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-video-download', async (req, res) => {
    try {
        const { phone, videoUrl, caption = '', session } = req.body;

        if (!phone || !videoUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL del video son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        if (!activeSocket) {
            return res.status(500).json({ status: false, message: 'WhatsApp no está conectado' });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`🎥 Descargando y enviando video desde URL a ${formattedNumber}`);

        try {
            // Validar que la URL del video no esté vacía
            if (!videoUrl || typeof videoUrl !== 'string' || videoUrl.trim() === '') {
                throw new Error('La URL del video es inválida o está vacía');
            }
            
            // Procesar URL de Google Drive si es necesario
            let processedUrl = videoUrl;
            if (videoUrl.includes('drive.google.com')) {
                const driveIdMatch = videoUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
                if (driveIdMatch) {
                    const fileId = driveIdMatch[1];
                    processedUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;
                    console.log(`🔄 URL de Google Drive convertida: ${processedUrl}`);
                } else {
                    throw new Error('No se pudo extraer el ID del archivo de Google Drive');
                }
            }

            // Descargar el video
            console.log('📥 Descargando video...');
            const videoResponse = await Promise.race([
                axios.get(processedUrl, {
                    responseType: 'arraybuffer',
                    timeout: 60000, // 60 segundos para descarga
                    maxContentLength: 100 * 1024 * 1024 // Máximo 100MB
                }),
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Timeout al descargar el video')), 60000)
                )
            ]);

            const videoBuffer = Buffer.from(videoResponse.data);
            console.log(`📊 Video descargado: ${(videoBuffer.length / 1024 / 1024).toFixed(2)} MB`);

            // Verificar el tipo de contenido
            const contentType = videoResponse.headers['content-type'];
            if (!contentType || !contentType.startsWith('video/')) {
                throw new Error(`El recurso no es un video válido: ${contentType}`);
            }

            // Enviar el video como buffer sin caption
            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, {
                    video: videoBuffer,
                    mimetype: contentType
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar video')), 30000))
            ]);

            console.log('✅ Video enviado correctamente como buffer');

            res.status(200).json({
                status: true,
                message: 'Video descargado y enviado correctamente',
                data: {
                    phone: formattedNumber,
                    videoUrl: videoUrl,
                    size: `${(videoBuffer.length / 1024 / 1024).toFixed(2)} MB`,
                    contentType: contentType
                }
            });

        } catch (downloadError) {
            console.error('Error al descargar o enviar video:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al descargar o enviar el video',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al procesar video:', error);
        res.status(500).json({
            status: false,
            message: 'Error al procesar video',
            error: error.message
        });
    }
});

/**
 * Endpoint para consultar el estado de conexión de WhatsApp
 */
app.get('/api/status', (req, res) => {
    const connected = !!globalSocket1;
    res.json({ 
        connected: connected,
        status: connected ? 'connected' : 'disconnected'
    });
});

/**
 * Endpoint para obtener los mensajes entrantes de WhatsApp (opcional)
 */
app.get('/api/messages', (req, res) => {
    res.json({ messages: newMessages });
});

/**
 * Endpoint de health check para verificar el estado del servicio
 */
app.get('/health', (req, res) => {
    const status = {
        status: 'ok',
        timestamp: new Date().toISOString(),
        whatsapp: {
            connected: !!globalSocket1,
            status: globalSocket1 ? 'connected' : 'disconnected'
        },
        environment: {
            node_env: process.env.NODE_ENV || 'development',
            port: PORT,
            api_url: process.env.URL_N8N || 'http://localhost:8000/api/v1/chat'
        }
    };
    res.json(status);
});

/**
 * Envía un mensaje de voz (PTT - Push to Talk) desde una URL
 * @param {Object} req - Objeto de solicitud HTTP con phone, audioUrl
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-voice-message', async (req, res) => {
    try {
        const { phone, audioUrl, session } = req.body;

        if (!phone || !audioUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL del audio son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        if (!activeSocket) {
            return res.status(500).json({ status: false, message: 'WhatsApp no está conectado' });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`🎤 Enviando mensaje de voz desde URL a ${formattedNumber}`);

        try {
            // Validar que la URL del audio no esté vacía
            if (!audioUrl || typeof audioUrl !== 'string' || audioUrl.trim() === '') {
                throw new Error('La URL del audio es inválida o está vacía');
            }
            
            // Verificar si la URL es válida antes de enviarla
            let isOggOpus = false;
            if (audioUrl.startsWith('http')) {
                try {
                    // Verificar si el audio existe y es accesible
                    const response = await Promise.race([
                        axios.head(audioUrl),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Timeout al verificar el audio')), 10000)
                        )
                    ]);
                    
                    // Verificar si la respuesta contiene un tipo de contenido de audio
                    const contentType = response.headers['content-type'];
                    if (!contentType || !contentType.startsWith('audio/')) {
                        throw new Error(`El recurso no es un audio válido: ${contentType}`);
                    }
                    isOggOpus = /audio\/ogg/.test(contentType) || /opus/i.test(contentType);
                    console.log(`📊 Audio válido para mensaje de voz: ${contentType} (voiceNote=${isOggOpus})`);
                } catch (urlError) {
                    console.error('Error al verificar la URL del audio:', urlError.message);
                    throw new Error(`URL de audio inválida o inaccesible: ${urlError.message}`);
                }
            } else if (!fs.existsSync(audioUrl)) {
                // Si es una ruta local, verificar que el archivo exista
                throw new Error(`El archivo de audio no existe en la ruta: ${audioUrl}`);
            }

            // Enviar el mensaje de voz con ptt: true; convertir si no es OGG Opus
            let result;
            if (isOggOpus && audioUrl.startsWith('http')) {
                // Ya es OGG Opus accesible por URL
                result = await Promise.race([
                    activeSocket.sendMessage(formattedNumber, {
                        audio: { url: audioUrl },
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true
                    }),
                    new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar mensaje de voz')), 25000))
                ]);
            } else {
                // Descargar y convertir a OGG Opus
                let sourceBuffer = null;
                if (audioUrl.startsWith('http')) {
                    const getResp = await axios.get(audioUrl, { responseType: 'arraybuffer', timeout: 30000 });
                    sourceBuffer = Buffer.from(getResp.data);
                } else {
                    sourceBuffer = await fs.promises.readFile(audioUrl);
                }
                const oggBuffer = await transcodeBufferToOggOpus(sourceBuffer);
                result = await Promise.race([
                    activeSocket.sendMessage(formattedNumber, {
                        audio: oggBuffer,
                        mimetype: 'audio/ogg; codecs=opus',
                        ptt: true
                    }),
                    new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar mensaje de voz')), 25000))
                ]);
            }

            console.log('✅ Mensaje de voz enviado correctamente');

            res.status(200).json({
                status: true,
                message: 'Mensaje de voz enviado correctamente',
                data: {
                    phone: formattedNumber,
                    audioUrl: audioUrl
                }
            });

        } catch (downloadError) {
            console.error('Error al enviar mensaje de voz:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al enviar el mensaje de voz',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al procesar mensaje de voz:', error);
        res.status(500).json({
            status: false,
            message: 'Error al procesar mensaje de voz',
            error: error.message
        });
    }
});

/**
 * Envía una imagen desde una URL sin validación estricta (útil para URLs que redirigen)
 * @param {Object} req - Objeto de solicitud HTTP con phone, imageUrl y caption
 * @param {Object} res - Objeto de respuesta HTTP
 */
app.post('/api/send-image-url-force', async (req, res) => {
    try {
        const { phone, imageUrl, caption = '', session } = req.body;

        if (!phone || !imageUrl) {
            return res.status(400).json({ 
                status: false, 
                message: 'El número de teléfono y la URL de la imagen son obligatorios' 
            });
        }

        // Seleccionar socket según preferencia o asociación por teléfono
        const phoneDigits = String(phone || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        if (!activeSocket) {
            return res.status(500).json({ status: false, message: 'WhatsApp no está conectado' });
        }

        // Formatear el número de teléfono
        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`📸 Enviando imagen (sin validación) desde URL a ${formattedNumber}`);

        try {
            // Validar que la URL de la imagen no esté vacía
            if (!imageUrl || typeof imageUrl !== 'string' || imageUrl.trim() === '') {
                throw new Error('La URL de la imagen es inválida o está vacía');
            }
            
            // Procesar la URL para manejar casos especiales
            let processedImageUrl = processImageUrl(imageUrl);
            if (processedImageUrl !== imageUrl) {
                console.log(`🔄 URL procesada: ${imageUrl} -> ${processedImageUrl}`);
            }

            console.log(`⚠️ Enviando imagen sin validación estricta: ${processedImageUrl}`);

            // Enviar la imagen sin validación previa
            const result = await Promise.race([
                activeSocket.sendMessage(formattedNumber, {
                    image: { url: processedImageUrl },
                    caption: caption
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar imagen')), 25000))
            ]);

            console.log('✅ Imagen enviada sin validación previa');

            res.status(200).json({
                status: true,
                message: 'Imagen enviada correctamente (sin validación previa)',
                data: {
                    phone: formattedNumber,
                    originalUrl: imageUrl,
                    processedUrl: processedImageUrl,
                    caption: caption
                }
            });

        } catch (downloadError) {
            console.error('Error al enviar imagen sin validación:', downloadError);
            return res.status(400).json({
                status: false,
                message: 'Error al enviar la imagen',
                error: downloadError.message
            });
        }

    } catch (error) {
        console.error('Error al procesar imagen sin validación:', error);
        res.status(500).json({
            status: false,
            message: 'Error al procesar imagen sin validación',
            error: error.message
        });
    }
});

// Endpoint para enviar ubicación vía WhatsApp
app.post('/api/send-location', async (req, res) => {
    try {
        const { number, session } = req.body;
        if (!number) {
            return res.status(400).json({ success: false, error: 'Faltan datos: number' });
        }
        const phoneDigits = String(number || '').replace(/[^\d]/g, '');
        const activeSocket = getSocketForDelivery(phoneDigits, session);
        if (!activeSocket) {
            return res.status(500).json({ success: false, error: 'WhatsApp no está conectado' });
        }

        const formattedNumber = phoneDigits + '@s.whatsapp.net';
        console.log(`📍 Enviando ubicación a ${formattedNumber}`);

        const locationMessage = {
            location: {
                degreesLatitude: 5.03829,
                degreesLongitude: -75.44636,
                name: 'Restaurante Juanchito Plaza',
                address: 'Km 13 Via Magdalena, Manizales, Caldas'
            }
        };

        try {
            await Promise.race([
                activeSocket.sendMessage(formattedNumber, locationMessage),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout al enviar ubicación')), 25000))
            ]);
            return res.json({ success: true, message: 'Ubicación enviada correctamente' });
        } catch (error) {
            return res.status(500).json({ success: false, error: error.message || 'Error al enviar ubicación' });
        }
    } catch (error) {
        return res.status(500).json({ success: false, error: error.message || 'Error general' });
    }
});

// Inicia el servidor y conecta a WhatsApp
server.listen(PORT, async () => {
    console.log(`🚀 Servidor escuchando en http://localhost:${PORT}`);
    
    // Conectar una sola sesión
    console.log('🔄 Iniciando conexión de WhatsApp (una sola sesión)...');
    await connectToWhatsApp('session1', globalSocket1, isConnecting1, reconnectAttempts1);
});

// Resolver binario de ffmpeg (usar ffmpeg-static si está instalado)
let FFMPEG_BIN = 'ffmpeg';
try {
    // eslint-disable-next-line global-require
    FFMPEG_BIN = require('ffmpeg-static') || 'ffmpeg';
} catch (e) {
    console.warn('⚠️ ffmpeg-static no instalado; se intentará usar ffmpeg del sistema');
}

/**
 * Transcodifica un buffer de audio a OGG Opus usando ffmpeg
 * Retorna un Buffer con el audio en `audio/ogg; codecs=opus`.
 * @param {Buffer} inputBuffer - Buffer de entrada (mp3/wav/etc.)
 * @returns {Promise<Buffer>}
 */
async function transcodeBufferToOggOpus(inputBuffer) {
    const tmpDir = os.tmpdir();
    const unique = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const inPath = path.join(tmpDir, `in_${unique}.tmp`);
    const outPath = path.join(tmpDir, `out_${unique}.ogg`);
    await fs.promises.writeFile(inPath, inputBuffer);
    return new Promise((resolve, reject) => {
        const args = [
            '-y',
            '-i', inPath,
            '-vn',
            '-ac', '1',
            '-ar', '48000',
            '-c:a', 'libopus',
            '-b:a', '64k',
            outPath
        ];
        execFile(FFMPEG_BIN, args, async (err) => {
            const cleanup = async () => {
                try { await fs.promises.unlink(inPath); } catch {}
                try { await fs.promises.unlink(outPath); } catch {}
            };
            if (err) {
                await cleanup();
                return reject(err);
            }
            try {
                const output = await fs.promises.readFile(outPath);
                await cleanup();
                return resolve(output);
            } catch (readErr) {
                await cleanup();
                return reject(readErr);
            }
        });
    });
}
