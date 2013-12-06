pro palsar_amplitude_to_db
    ; TODO: Write the description about what this program does
    ; TODO: Implement this script for other SAR sensors.
    ; Author(s): 
    ;          Rachel Melrose, rachel.melrose@ga.gov.au
    ;          Josh Sixsmith, joshua.sixsmith@ga.gov.au

    base_cwd     = 'C:\SAR\SAR_DATA\ALOSPALSAR\new_flood'
    output_dir   = 'C:\SAR\SAR_DATA\ALOSPALSAR\db\'
    summary_file = 'summary.txt'
    file_list_HH = file_search(base_cwd,'IMG-HH*.5GUA')
    file_list_HV = file_search(base_cwd,'IMG-HV*.5GUA')

    for i=0, n_elements(file_list_HH)-1 do begin
        fname     = file_list_HH[i]
        base_name = file_basename(fname, '.5GUA') 
        dir_name  = file_dirname(fname)
        
        cd, dir_name
        exists = file_test(summary_file)
        
        if exists ne 1 then continue ;go to next loop
        
        summary_info = JS_Read_Ascii(summary_file)
        
        ; We know that we're interested in the last element of summary info
        ; So get the last element which is the scene observation date
        obs_date = summary_info[n_elements(summary_info)-1]
        p1 = strpos(obs_date, '"')
        p2 = strpos(obs_date, '"', /reverse_search)
        length = p2 - p1
        obs_date = strmid(obs_date, p1+1, length-1)
        
        ; Output filenames
        out_db_fname  = output_dir + base_name + '_' + obs_date
        out_lee_fname = out_db_fname + 'lee'
        
        ; Convert the HH data to db (decibel units)
        envi_open_data_file, fname, /alos, r_fid=fid
        envi_file_query, fid, dims=dims, nb=nb
        pos = lindgen(nb)
        expr = '10*alog10(float(b1)/10000)' ; convert to db
        envi_doit, 'MATH_DOIT', fid=fid, dims=dims, exp=expr, out_name=out_db_fname, $
            r_fid=db_fid, pos=pos
        
        ; Apply Lee filter to the db file created above
        method = 0
        kx = 3
        mult_mean = 1.0
        noise_type = 1
        sigma= 0.25
        envi_doit, 'ADAPT_FILT_DOIT', dims=dims, fid=db_fid, pos=pos, out_name=out_lee_fname, $
            r_fid=lee_fid, method=method, kx=kx, mult_mean=mult_mean, noise_type=noise_type, $
            sigma=sigma
        
    endfor

    for i=0, n_elements(file_list_HV)-1 do begin
        fname     = file_list_HV[i]
        base_name = file_basename(fname, '.5GUA') 
        dir_name  = file_dirname(fname)
        
        cd, dir_name
        exists = file_test(summary_file)
        
        if exists ne 1 then continue ;go to next loop
        
        summary_info = JS_Read_Ascii(summary_file)
        
        ; We know that we're interested in the last element of summary info
        ; So get the last element which is the scene observation date
        obs_date = summary_info[n_elements(summary_info)-1]
        p1 = strpos(obs_date, '"')
        p2 = strpos(obs_date, '"', /reverse_search)
        length = p2 - p1
        obs_date = strmid(obs_date, p1+1, length-1)
        
        ; Output filenames
        out_db_fname  = output_dir + base_name + '_' + obs_date
        out_lee_fname = out_db_fname + 'lee'
        
        ; Convert the HH data to db (decibel units)
        envi_open_data_file, fname, /alos, r_fid=fid
        envi_file_query, fid, dims=dims, nb=nb
        pos = lindgen(nb)
        expr = '10*alog10(float(b1)/10000)' ; convert to db
        envi_doit, 'MATH_DOIT', fid=fid, dims=dims, exp=expr, out_name=out_db_fname, $
            r_fid=db_fid, pos=pos
        
        ; Apply Lee filter to the db file created above
        method = 0
        kx = 3
        mult_mean = 1.0
        noise_type = 1
        sigma= 0.25
        envi_doit, 'ADAPT_FILT_DOIT', dims=dims, fid=db_fid, pos=pos, out_name=out_lee_fname, $
            r_fid=lee_fid, method=method, kx=kx, mult_mean=mult_mean, noise_type=noise_type, $
            sigma=sigma
        
    endfor

end