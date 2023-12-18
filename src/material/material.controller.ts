import { Controller } from '@nestjs/common';
import { MaterialService } from 'src/material/material.service';

@Controller('material')
export class MaterialController {
  constructor(private readonly materialService: MaterialService) {}
}
