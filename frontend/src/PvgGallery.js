import React, { useState } from 'react';

import { Link, Chip, Grid, Typography, Drawer, Box, TextField } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';

import Pagination from "material-ui-flat-pagination";
import Carousel, { Modal, ModalGateway } from 'react-images';
import Gallery from 'react-photo-gallery';

import { animateScroll } from 'react-scroll'

import { host, IMAGES_PER_PAGE } from './env.js';

const useStyles = makeStyles({
    mr: {
        marginRight: '0.5em'
    },
    md: {
        marginDown: '1em'
    }
});

function ImageCaption(props) {
    const classes = useStyles();

    const img = props.img;
    const illust_url = 'https://www.pixiv.net/artworks/' + img.pid.toString(),
          author_url = 'https://www.pixiv.net/member.php?id=' + img.aid.toString();

    return (
        <Typography>
            <div className={classes.md}>
                <Link
                    href={illust_url}
                    target="_blank"
                    rel="noreferrer"
                    className={classes.mr}
                >{img.title}</Link>
                <Link
                    href={author_url}
                    target="_blank"
                    rel="noreferrer"
                >{img.author}</Link>
            </div>
            {img.tags.map(tag =>
                <Chip
                    className={classes.mr}
                    label={tag}
                    onClick={ () => {
                        props.close_modal();
                        props.update_tags(tag, img.ori);
                    }}
                />
            )}
        </Typography>
    );
}

function GalleryView(props) {
    const [index, set_index] = useState(-1);

    const close_modal = () => set_index(-1);

    return (
        <>
            <Gallery photos={props.images} onClick={ (e, {index}) => set_index(index) } />
            <ModalGateway>
                {index >= 0 ? (
                <Modal onClose={close_modal}>
                    <Carousel
                        currentIndex={index}
                        views={props.views.map(view => ({
                            source: host + view.img.ori,
                            caption: <ImageCaption img={view.img} update_tags={view.update_tags} close_modal={close_modal} />
                        }))}
                    />
                </Modal>
                ) : null}
            </ModalGateway>
        </>
    );
}

function PaginationInput(props) {
    const [val, set_val] = useState(1);

    return (
        <Box m={-0.3} ml={3}>
            <TextField
                style={{
                    width: 70
                }}
                inputProps={{
                    style: {
                        fontSize: '90%'
                    }
                }}
                margin="dense"
                size="small"
                type="number"
                onChange={ e => {
                    const nv = e.target.value;
                    if (nv === '')
                        set_val(0);
                    else {
                        const x = parseInt(nv, 10);
                        if ((x >= 1 && x <= props.tot) || x < val)
                            set_val(x);
                        else
                            e.target.value = val;
                    }
                }}
                onKeyPress={ e => {
                    if (e.key === 'Enter' && val >= 1 && val <= props.tot) 
                        props.switch(val - 1);
                }}
            />
        </Box>
    );
}

function GalleryPagination(props) {
    const [off, set_offset] = useState(props.default_offset);

    const tot = props.pages.length;
    let images, views;
    if (off < tot) {
        images = props.pages[off];
        views = props.modal_pages[off];
    } else
        images = views = [];

    return (
        <>
            <Box m={3}>
                <GalleryView
                    images={images}
                    views={views}
                />
            </Box>
            <Drawer
                variant="permanent"
                anchor="bottom"
                elevation={100}
            >
                <Grid container justify="center">
                    <Pagination
                        limit={1}
                        offset={off}
                        total={tot}
                        onClick={(e, offset) => {
                            set_offset(offset);
                            animateScroll.scrollToTop({duration: 200});
                        }}
                        otherPageColor="primary"
                        innerButtonCount={3}
                        outerButtonCount={3}
                    />
                    <PaginationInput switch={set_offset} tot={tot} />
                </Grid>
            </Drawer>
        </>
    );
}

export default function PvgGallery(props) {
    let pages = [], modal_pages = [], page = [], modal_page = [], offset = 0, ha = 0, hs = 0;

    for (const img of props.images) {
        ha ^= img.pid + img.w;
        hs += img.pid + img.h;

        if (img.ori === props.locating_id)
            offset = pages.length;

        page.push({
            src: host + img.thu,
            width: img.w,
            height: img.h
        });
        modal_page.push({
            img,
            update_tags: props.update_tags
        });

        if (page.length >= IMAGES_PER_PAGE) {
            pages.push(page);
            modal_pages.push(modal_page);
            page = [];
            modal_page = [];
        }
    }
    if (page.length) {
        pages.push(page);
        modal_pages.push(modal_page);
    }

    console.log('hash', ha, hs);
    return (
        <GalleryPagination
            pages={pages}
            modal_pages={modal_pages}
            default_offset={offset}
            key={[ha, hs]}
        />
    );
}
