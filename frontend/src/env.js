const host = (process.env['NODE_ENV'] === 'development') ? 
    'http://127.0.0.1:5678/' : (
    window.location.protocol + '//' +
    window.location.hostname +
    (window.location.port ? ':' + window.location.port + '/' : '/'));

const images_per_page = 50;

export { host, images_per_page };
